import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from PIL import Image
from streamlit_paste_button import paste_image_button
from streamlit_drawable_canvas import st_canvas
import json
import re
import base64
import os
import numpy as np
from video import show_guidde_video
from io import BytesIO
from PIL import Image
from pathlib import Path
import datetime
from streamlit_oauth import OAuth2Component
import jwt
import copy

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "https://829w23be5rbdxam99fd4do.streamlit.app")
oauth2 = OAuth2Component(
    CLIENT_ID, 
    CLIENT_SECRET, 
    "https://accounts.google.com/o/oauth2/v2/auth", 
    "https://oauth2.googleapis.com/token", 
    "https://oauth2.googleapis.com/token", 
    "https://oauth2.googleapis.com/revoke"
)
genai.configure(api_key=GOOGLE_API_KEY)
electrical_advisor_flag = 0
derivation_steps_flag = 0
img, topology, analysis_request, circuit_uses = None, None, None, None
performance_advice, power_advice, noise_advice, component_advice, Recommended_articles_links = None, None, None, None, None
model = genai.GenerativeModel('gemini-2.5-pro')

def load_static_file(filename):
    """Load content from static file"""
    file_path = os.path.join('static', filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"Static file not found: {filename}")
        return ""

def encode_css_base64(css_content):
    """Encode CSS content as base64 for inline embedding"""
    return base64.b64encode(css_content.encode('utf-8')).decode('utf-8')

def generate_calculator_html(z_latex, params=[]):
    """Generate the calculator HTML using templates"""
    # Load static files
    html_template = load_static_file('desmos_calculator.html')
    css_content = load_static_file('calculator.css')
    js_content = load_static_file('desmos_calculator.js')
    
    if not all([html_template, css_content, js_content]):
        return "<div>Error loading calculator resources</div>"
    
    # Encode CSS for inline embedding
    css_base64 = encode_css_base64(css_content)
    
    # Replace template placeholders using string replacement (safer than .format())
    html_content = html_template.replace('{css_base64}', css_base64)
    html_content = html_content.replace('{calculator_js}', js_content)
    html_content = html_content.replace('{z_latex}', json.dumps(z_latex))
    html_content = html_content.replace('{params}', json.dumps(params))
    
    return html_content

def generate_electrical_schematic_draw():
    html_template = load_static_file('circuit_diagram.html')
    css_content = load_static_file('diagram.css')
    js_content = load_static_file('circuit_diagram.js')
    #if not all([html_template, css_content, js_content]):
    #   return "<div>Error loading calculator resources</div>"
    css_base64 = encode_css_base64(css_content)
    return html_template

def electrical_advisor(image, topology, analysis_request, circuit_uses):
    prompt = """
    You are an expert Analog IC Design Engineer.
    Input provided:
        {"- An image of the schematic" if image else ""}
        {"- Analysis request: " + analysis_request if image else ""}
        {"- Circuit use cases: " + circuit_uses if circuit_uses else ""}
    Based on the provided circuit diagram and analysis request, provide detailed advice on how to optimize the circuit for the specified use cases.
    Consider factors such as performance, power consumption, noise, and component selection. Provide specific recommendations for improving the circuit design to better meet the requirements of the use cases.
    Output ONLY a valid JSON object:
    {
        "performance_advice": "Detailed advice on improving performance",
        "power_advice": "Detailed advice on reducing power consumption",
        "noise_advice": "Detailed advice on minimizing noise",
        "component_advice": "Specific recommendations for component selection and values",
        "Recommended_articles_links": "Recommendation for articles ONLY related to the circuit (ONLY from reliable sources: IEEE, JSSC, etc.), similar circuits, similar architectures, etc. give a links to the articles in this format: "Article 1, Article 2, Article 3, ..." 
    }
    """
    content_inputs = [prompt]
    if image:
        content_inputs.append(image)
    if analysis_request:
        content_inputs.append(f"Analysis Request:\n{analysis_request}")
    if circuit_uses:
        content_inputs.append(f"Circuit Use Cases:\n{circuit_uses}")   
    response = model.generate_content(content_inputs)
    text = response.text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        try:
            # Clean the JSON string to remove control characters
            json_str = match.group()
            # Remove common problematic control characters
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response.text[:500]}...")
            return None
    return None 

def bug_detector(image, topology, formula, analysis_request, circuit_uses):
    model = genai.GenerativeModel('gemini-2.5-pro')
    prompt = """
    You are a strict Senior Analog VLSI Design Reviewer. 
    Analyze the provided schematic and circuit information to detect any architectural bugs, incorrect connections, or fundamental design flaws.
    
    Input provided:
    - Topology: {topology if topology else 'Unknown'}
    - Derived Formula: {formula if formula else 'Unknown'}
    - Analysis Request: {analysis_request if analysis_request else 'Unknown'}
    - Circuit Use Cases: {circuit_uses if circuit_uses else 'Unknown'}
    
    Look specifically for issues such as:
    - Floating nodes, missing DC bias paths, or missing ground references.
    - Transistors lacking proper biasing elements or connected in ways that force them out of their desired operating region.
    - Missing compensation (e.g., Miller, lead-lag) in feedback loops leading to potential instability.
    - Shorted inputs/outputs or incorrect polarity in differential pairs.
    - Unrealistic component configurations given the stated use case.
    
    Output ONLY a valid JSON object matching this exact format:
    {{
        "bug_found": "Yes" or "No",
        "severity": "None/Low/Medium/High/Critical",
        "bug_description": "Detailed engineering explanation of the specific bugs or topological flaws found. If none, write 'No structural bugs detected.'",
        "suggested_fix": "Actionable instructions on how to fix the identified issues. If none, write 'N/A'"
    }}
    """
    
    content_inputs = [prompt]
    if image:
        content_inputs.append(image)
        
    response = model.generate_content(content_inputs)
    text = response.text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    
    if match:
        try:
            json_str = match.group()
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None
    return None

def analyze_circuit(image, netlist_text, analysis_request, derivation_steps_flag):
    model = genai.GenerativeModel('gemini-2.5-pro')
    prompt = """
    You are an expert Analog IC Design Engineer.
    Input provided:
        {"- An image of the schematic" if image else ""}
        {"- A SPICE netlist describing the connectivity" if netlist_text else ""}
    Analyze the provided circuit diagram (circuit schematic image or netlist file) **based only on the user's request: "{analysis_request}"**. (can be Z(Vout), Vout/Vin, Vout/Vcc etc.).
    Extract the symbolic formula for the given node or function.
    Include all elements (R, L, C).
    Include active elements (nmos, pmos etc.) model it by small signal model (current source, g_m and r_o).
    Output ONLY a valid JSON object:
    {
      "topology": "Topology Name",
      "H_latex_formula": "formula using s, R, C, L, g_m, r_o in regular LaTex format, The expression should be as simplified as possible. Do not use the || (parallel) symbol, but simplify the equation as much as possible. do not neglect any parameter. do not use in prohibited LaTex letters like: ',', ';' etc.",
      "H_latex": "formula using s, R, C, L, g_m, r_o. use the Desmos calculator LaTex format only. for example: {5+a_{2}}/{s^{2}+\\\\pi*s-{1}/{5*s}}. use * for multiply, / for divition. any nominator or denominator, put in parentheses: '()'. the function name will be: Z(s) if it is impedance, H(s) if it is a transfer function."
      "params": ["list of all the parameters that appear in the formula, for example: ['R1', 'C2', 'gm3', 'ro4']"]
    }
    """
    if derivation_steps_flag == 1:
        prompt += """derivation_steps": "In addition to the above, provide a detailed step-by-step derivation of how you arrived at the final formula. Include all intermediate steps, assumptions, and simplifications made during the analysis. write it in LaTex format only."""
    content_inputs = [prompt]
    if image:
        content_inputs.append(image)
    if netlist_text:
        pass
        #content_inputs.append(f"Netlist Data:\n{netlist_text}")
    if analysis_request:
        content_inputs.append(f"Analysis Request:\n{analysis_request}")
    response = model.generate_content(content_inputs)
    text = response.text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        try:
            # Clean the JSON string to remove control characters
            json_str = match.group()
            # Remove common problematic control characters
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response.text[:500]}...")
            return None
    return None

def optimize_circuit(bounded_param_list, image, formula, analysis_request, circuit_uses):
    model = genai.GenerativeModel('gemini-2.5-pro')
    prompt = """
    You are an expert Analog IC Design Engineer.
    Input provided:
        {"- An image of the schematic" if image else ""}
        {"- A symbolic formula for the circuit behavior: " + formula if formula else ""}
        {"- Analysis request: " + analysis_request if analysis_request else ""}
        {"- Circuit use cases: " + circuit_uses if circuit_uses else ""}
        
    Based on the provided circuit diagram, symbolic formula, and analysis request, optimize the circuit design by tuning the following parameters within their specified bounds:
    {bounded_param_list}
    
    CRITICAL INSTRUCTIONS FOR OUTPUT:
    1. The "optimized_parameters" values MUST BE EXACT ALPHANUMERIC STRINGS representing the calculated numerical value and its engineering prefix (e.g., "100f", "5p", "10n", "2.5u", "50m", "10", "1k", "10M").
    2. DO NOT output ANY descriptive text or explanations (like "maximum of range") inside the "optimized_parameters" values. 
    3. Put all your reasoning, explanations, and descriptions ONLY in the "optimization_advice" string.
    4. use only the provided parameters in the optimization and do not add any new parameter that is not in the list.

    Output ONLY a valid JSON object matching this exact format:
    {{
        "optimized_parameters": {{
            "param_name": "exact_value_with_prefix"
        }},
        "optimization_advice": "Detailed advice on how to adjust the parameters and why"
    }}
    """
    content_inputs = [prompt]
    if image:
        content_inputs.append(image)
    if formula:
        content_inputs.append(f"Symbolic Formula:\n{formula}")
    if analysis_request:
        content_inputs.append(f"Analysis Request:\n{analysis_request}")
    if circuit_uses:
        content_inputs.append(f"Circuit Use Cases:\n{circuit_uses}")   
    response = model.generate_content(content_inputs)
    text = response.text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        try:
            json_str = match.group()
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response.text[:500]}...")
            return None
    return None

def assign_param_bounds(param_list):
    bounds_config = {
        'gm': (1e-3, 500e-3),
        'R':  (1, 1000),
        'C':  (1e-15, 10e-12),
        'L':  (50e-12, 500e-12),
        'r': (1,10000),
        'A': (0.1,100000)
    }  
    def format_latex_name(name):
            name = str(name)
            if '_' in name:
                parts = name.split('_', 1)
                base = parts[0]
                sub = parts[1].replace('{', '').replace('}', '')
                return f"{base}_{{{sub}}}"
            if len(name) > 1:
                return f"{name[0]}_{{{name[1:]}}}"
            return name
    def format_unit(val):
        if val == 0: 
            return "0"
        abs_val = abs(val)
        if 1e-15 <= abs_val < 1e-12:
            return f"{val * 1e15:g}f"
        elif 1e-12 <= abs_val < 1e-9:
            return f"{val * 1e12:g}p"
        elif 1e-9 <= abs_val < 1e-6:
            return f"{val * 1e9:g}n"
        elif 1e-6 <= abs_val < 1e-3:
            return f"{val * 1e6:g}u"
        elif 1e-3 <= abs_val < 1:
            return f"{val * 1e3:g}m"
        elif 1e3 <= abs_val < 1e6:
            return f"{val / 1e3:g}k"
        elif 1e6 <= abs_val < 1e9:
            return f"{val / 1e6:g}M"
        return f"{val:g}"
    result = []
    for param in param_list:
        name = str(param) 
        min_val, max_val = 0, 0 
        if name.startswith('gm'):
            min_val, max_val = bounds_config['gm']
        elif name.startswith('R'):
            min_val, max_val = bounds_config['R']
        elif name.startswith('C'):
            min_val, max_val = bounds_config['C']
        elif name.startswith('L'):
            min_val, max_val = bounds_config['L']
        elif name.startswith('r'):
            min_val, max_val = bounds_config['r']
        elif name.startswith('A'):
            min_val, max_val = bounds_config['A']    
        else:
            print(f"Warning: Unknown parameter type for '{name}'")
            continue 
        value = (min_val + max_val) / 2
        step = (max_val - min_val) / 100
        result.append({
            "name": format_latex_name(name),
            "value": format_unit(value),
            "min": format_unit(min_val),
            "max": format_unit(max_val),
            "step": format_unit(step)
        })
    return result

def image_to_base64(img):
    if img is None:
        return None
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def base64_to_image(base64_str):
    if not base64_str:
        return None
    img_data = base64.b64decode(base64_str)
    img = Image.open(BytesIO(img_data))
    return img

def create_project_export(project_data):
    export_dict = project_data.copy()
    if export_dict.get('res'):
        export_dict['res'] = project_data['res'].copy()
        params_list = export_dict['res'].get('params', [])
        live_params = {}
        for p in params_list:
            widget_key = f"manual_input_{p}"
            val = st.session_state.get(widget_key, "").strip()
            live_params[p] = val   
        export_dict['res']['live_params_values'] = live_params
    export_dict["img"] = image_to_base64(project_data.get("img"))
    if 'user_info' in st.session_state:
        export_dict["author_name"] = st.session_state['user_info'].get('name', 'Unknown')
        export_dict["author_email"] = st.session_state['user_info'].get('email', 'Unknown')
    return json.dumps(export_dict, indent=4)

def render_save_project_section(project_data):
    # Nadine: We need to set this function to save in the common folder in sharepoint. 
    # Note: Since the app is deployed on a server/container, we use download_button 
    # and instruct users to point their browser download to the SharePoint sync folder.
    res = project_data.get('res')
    if not res:
        return 
    st.markdown("---")
    st.subheader("💾 Save Project")
    st.write("📝 **Set Parameter Values Before Saving:**")
    raw_params = res.get('params', [])
    if isinstance(raw_params, str): 
        raw_params = [raw_params]
    params_list = []
    for p in raw_params:
        p_str = str(p).strip()
        if p_str and p_str not in params_list:
            params_list.append(p_str)
    if 'live_params_values' not in res or res['live_params_values'] is None:
        st.session_state['project_data']['res']['live_params_values'] = {}
    if params_list:
        cols = st.columns(3)
        for i, param_name in enumerate(params_list):
            with cols[i % 3]:
                existing_val = res.get('live_params_values', {}).get(param_name, "")
                val = st.text_input(
                    label=f"{param_name} Value:", 
                    value=existing_val,
                    key=f"manual_input_{param_name}",
                    placeholder="e.g., 10k, 5p"
                )
                st.session_state['project_data']['res']['live_params_values'][param_name] = val
    else:
        st.info("No parameters detected for manual input.")
    default_topology_name = res.get('topology', 'circuit_project')
    default_safe_name = re.sub(r'[\\/*?:"<>|]', "", str(default_topology_name)).replace(" ", "_")
    custom_filename = st.text_input(
        "📄 **Project Filename:**", 
        value=default_safe_name,
        help="Enter the name for your saved project file."
    )
    safe_filename = re.sub(r'[\\/*?:"<>|]', "", custom_filename).replace(" ", "_")
    if not safe_filename.endswith('.json'):
        safe_filename += '.json'
    json_export = create_project_export(project_data)
    st.info("💡 Tip: To save directly to your SharePoint folder, ensure your browser is set to 'Ask where to save each file before downloading'.")
    st.download_button(
        label=f"Download {safe_filename}",
        data=json_export,
        file_name=safe_filename,
        mime="application/json",
        use_container_width=True
    )

def render_feedback_section(project_data):
    if not project_data.get('res'):
        st.info("Analyze a circuit first to enable feedback and improvement suggestions.")
        return
    st.markdown("---")
    feedbacks = project_data.get('feedbacks', [])
    with st.expander("🚩 Report an Issue / Team Feedback", expanded=False):
        with st.form(key="feedback_form", clear_on_submit=True):
            feedback_type = st.selectbox("Type of issue:", ["Incorrect Formula", "Wrong Component Value", "Other"])
            feedback_text = st.text_area("Describe the mistake:", height=100)
            submit_button = st.form_submit_button("Submit Feedback to Project", use_container_width=True)
            if submit_button:
                if feedback_text.strip():
                    new_feedback = {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": feedback_type,
                        "description": feedback_text
                    }
                    if 'feedbacks' not in st.session_state['project_data']:
                        st.session_state['project_data']['feedbacks'] = []
                    st.session_state['project_data']['feedbacks'].append(new_feedback)
                    project_data = st.session_state['project_data'] 
                    st.success("Feedback recorded!")
        if feedbacks:
            st.markdown("**Previous Feedback on this circuit:**")
            for fb in feedbacks:
                st.caption(f"🕒 {fb['timestamp']} | **{fb['type']}**")
                st.write(f"> {fb['description']}")
            project_data = st.session_state['project_data']

def connection():
    if 'google_token' not in st.session_state:
        st.title("Connect Your Google Account")
        st.write("Please connect your Google account to start analyzing circuits with CirAI.")
        result = oauth2.authorize_button(
            name="Connect with Google",
            redirect_uri=REDIRECT_URI,
            scope="openid email profile",
            icon="https://www.google.com/favicon.ico",
            use_container_width=True
        )
        if result and 'token' in result:
            st.session_state['google_token'] = result.get('token')
            st.rerun()
        st.stop()
    token = st.session_state['google_token']
    user_info = jwt.decode(token['id_token'], options={"verify_signature": False}, algorithms=["RS256"])
    st.session_state['user_info'] = user_info
    with st.sidebar:
        st.write(f"Hello, **{user_info['name']}**")
        if st.button("Logout"):
            del st.session_state['google_token']
            del st.session_state['user_info']
            st.rerun()
        st.divider()

# --- GUI --- #
st.set_page_config(
    page_title="CirAI | AI Circuit Analysis & Analog IC Design Copilot",
    page_icon="⚡",
    layout="wide"
)
connection()
if 'project_data' not in st.session_state:
    st.session_state['project_data'] = {
        "img": None,
        "netlist_text": "",
        "analysis_request": "",
        "res": None,
        "advisor_res": None,
        "opt_res": None,
        "bug_res": None,
        "feedbacks": [] 
    }
st.title("CirAI | AI Circuit Analysis & Analog IC Design Copilot")
if 'res' not in st.session_state:
    st.session_state['res'] = None
col_in, col_out = st.columns([1, 2])

with col_in:
    st.header("1. Input (Image or Netlist)")
    uploaded_file = st.file_uploader("Upload project file", type=["json"])
    if uploaded_file is not None:
            file_content = uploaded_file.getvalue().decode("utf-8")
            if st.session_state.get('last_uploaded_file_content') != file_content:
                try:
                    loaded_data = json.loads(file_content)
                    img_data = loaded_data.get("img") or loaded_data.get("imag")
                    img_obj = base64_to_image(img_data)
                    if loaded_data.get("res"):
                        res_data = loaded_data["res"]
                    else:
                        res_data = {
                            "H_latex": loaded_data.get("H_latex") or loaded_data.get("formula", ""),
                            "H_latex_formula": loaded_data.get("H_latex_formula") or loaded_data.get("formula", ""),
                            "params": loaded_data.get("params", []),
                            "topology": loaded_data.get("topology", "Loaded Project (Legacy)")
                        }
                    st.session_state['project_data'].update({
                        'img': img_obj,
                        'netlist_text': loaded_data.get("netlist_text", ""),
                        'analysis_request': loaded_data.get("analysis_request", ""),
                        'circuit_uses': loaded_data.get("circuit_uses", ""),
                        'advisor_res': loaded_data.get("advisor_res"),
                        'opt_res': loaded_data.get("opt_res"),
                        'feedbacks': loaded_data.get("feedbacks", []),
                        'res': res_data
                    })
                    if 'live_params_values' in res_data:
                        st.session_state['manual_params'] = res_data['live_params_values']
                    st.session_state['last_uploaded_file_content'] = file_content
                    st.success("Project loaded successfully!")
                except Exception as e:
                    st.error(f"Error loading project: {e}")
    analysis_request = st.text_input("Function to analyze (for example: Vout/Vin, Z(Vout) etc.):", value="Vout")
    input_method = st.radio(
        "Select Input Method:", 
        ["🖼️ Upload / Paste", "✏️ Draw Circuit", "📝 Netlist", "Use circuit diagram"], 
        horizontal=True
    )
    img = st.session_state['project_data'].get('img')
    netlist_content = st.session_state['project_data'].get('netlist_text')
    if input_method == "🖼️ Upload / Paste":
        st.write("Upload or paste a circuit image:")
        uploaded_file = st.file_uploader("Upload circuit image", type=["png", "jpg", "jpeg"])
        paste_result = paste_image_button(label="📋 Paste here", errors="ignore")
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Uploaded circuit", width=350)
        elif paste_result.image_data is not None:
            st.image(paste_result.image_data, caption="Pasted circuit", width=350)
            img = paste_result.image_data
        elif img is not None:
            st.image(img, caption="Loaded circuit from project", width=350)
    elif input_method == "✏️ Draw Circuit":
            st.write("Draw your schematic directly (use standard symbols):")
            
            # 1. Initialize TWO separate states: one for the canvas to load, one to track what's drawn
            if "canvas_key" not in st.session_state:
                st.session_state["canvas_key"] = 0
            if "initial_drawing" not in st.session_state:
                st.session_state["initial_drawing"] = {"version": "4.4.0", "objects": []}
            if "current_canvas_state" not in st.session_state:
                st.session_state["current_canvas_state"] = {"version": "4.4.0", "objects": []}

            # 2. Helper function to add components
            def add_component(path_array, width, height):
                import copy
                # Take the LATEST state of what the user drew so far
                latest_state = copy.deepcopy(st.session_state["current_canvas_state"])
                if "objects" not in latest_state:
                    latest_state["objects"] = []
                    
                new_component = {
                    "type": "path",
                    "version": "4.4.0",
                    "originX": "left",
                    "originY": "top",
                    "left": 150,  
                    "top": 150,   
                    "width": width,
                    "height": height,
                    "fill": "transparent",
                    "stroke": "#000000",
                    "strokeWidth": 2,
                    "strokeLineCap": "round",
                    "strokeLineJoin": "round",
                    "path": path_array,
                    "selectable": True,
                    "evented": True
                }
                latest_state["objects"].append(new_component)
                
                # Update the starting point for the canvas, and bump the key to force it to render the new component
                st.session_state["initial_drawing"] = latest_state
                st.session_state["canvas_key"] += 1

            # 3. Component Paths
            resistor_path = [["M",0,10],["L",15,10],["L",20,0],["L",30,20],["L",40,0],["L",50,20],["L",55,10],["L",70,10]]
            capacitor_path = [["M",0,15],["L",25,15],["M",25,0],["L",25,30],["M",35,0],["L",35,30],["M",35,15],["L",60,15]]
            gnd_path = [["M",20,0],["L",20,20],["M",0,20],["L",40,20],["M",10,30],["L",30,30],["M",15,40],["L",25,40]]
            pmos_path = [["M", 0, 30], ["L", 15, 30], ["M", 15, 15], ["L", 15, 45],["M", 22, 15], ["L", 22, 45],["M", 22, 20], ["L", 40, 20], ["L", 40, 0],["M", 22, 40], ["L", 40, 40], ["L", 40, 60],["M", 31, 15], ["L", 25, 20], ["L", 31, 25]]
            nmos_path = [["M", 0, 30], ["L", 15, 30], ["M", 15, 15], ["L", 15, 45],["M", 22, 15], ["L", 22, 45],["M", 22, 20], ["L", 40, 20], ["L", 40, 0],["M", 22, 40], ["L", 40, 40], ["L", 40, 60],["M", 27, 35], ["L", 33, 40], ["L", 27, 45]]
            opamp_path = [["M", 20, 10], ["L", 20, 50], ["L", 60, 30], ["L", 20, 10],["M", 0, 20], ["L", 20, 20],["M", 0, 40], ["L", 20, 40],["M", 60, 30], ["L", 80, 30],["M", 24, 20], ["L", 30, 20],["M", 24, 40], ["L", 30, 40], ["M", 27, 37], ["L", 27, 43]]
            inductor_path = [["M", 0, 20], ["L", 10, 20], ["Q", 15, 0, 20, 20], ["Q", 25, 0, 30, 20], ["Q", 35, 0, 40, 20], ["Q", 45, 0, 50, 20], ["L", 60, 20]]
            
            # 4. Built-in Components Buttons
            st.write("**Add Components:**")
            col_btn1, col_btn2, col_btn3, col_btn4, col_btn5, col_btn6, col_btn7 = st.columns(7)
            with col_btn1:
                if st.button("➕ Resistor", use_container_width=True):
                    add_component(resistor_path, width=70, height=20)
            with col_btn2:
                if st.button("➕ Capacitor", use_container_width=True):
                    add_component(capacitor_path, width=60, height=30)
            with col_btn3:
                if st.button("➕ Inductor", use_container_width=True):
                    add_component(inductor_path, width=60, height=30)
            with col_btn4:
                if st.button("➕ nmos", use_container_width=True):
                    add_component(nmos_path, width=60, height=30)
            with col_btn5:
                if st.button("➕ pmos", use_container_width=True):
                    add_component(pmos_path, width=60, height=30)
            with col_btn6:
                if st.button("➕ OpAmp", use_container_width=True):
                    add_component(opamp_path, width=60, height=30)
            with col_btn7:
                if st.button("➕ Ground", use_container_width=True):
                    add_component(gnd_path, width=40, height=40)
                    
            st.divider()

            # 5. Tools configuration
            col_tools1, col_tools2 = st.columns([3, 1])
            with col_tools1:
                draw_tool = st.radio(
                    "Choose Tool:", 
                    ["✏️ Freehand", "📏 Line", "🧽 Eraser", "🖱️ Select/Delete"], 
                    horizontal=True
                )
            with col_tools2:
                stroke_width = st.slider("Thickness:", 1, 10, 2)
                
            if draw_tool == "✏️ Freehand":
                mode = "freedraw"
                color = "#000000"
            elif draw_tool == "📏 Line":
                mode = "line"
                color = "#000000"
            elif draw_tool == "🧽 Eraser":
                mode = "freedraw"
                color = "#ffffff"  
                stroke_width = stroke_width * 4  
            else: 
                mode = "transform"
                color = "#000000"
                st.info("💡 Click on any line or shape you drew and press 'Delete' on your keyboard to remove it.")

            # 6. Render Canvas 
            # Here we ONLY pass initial_drawing. It won't update continuously, stopping the flicker loop!
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=stroke_width,
                stroke_color=color, 
                background_color="#ffffff", 
                height=400,
                width=400,
                drawing_mode=mode,
                initial_drawing=st.session_state["initial_drawing"], 
                key=f"circuit_canvas_{st.session_state['canvas_key']}", 
            )

            # 7. Constantly save the user's progress secretly, so we don't lose it on the next button click
            if canvas_result.json_data is not None:
                st.session_state["current_canvas_state"] = canvas_result.json_data

            if canvas_result.image_data is not None:
                is_drawn = np.any(canvas_result.image_data[:, :, :3] != 255)
                if is_drawn:
                    rgba_img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    white_bg = Image.new("RGB", rgba_img.size, (255, 255, 255))
                    white_bg.paste(rgba_img, mask=rgba_img.split()[3]) 
                    img = white_bg
                    st.success("Drawing captured!")
    elif input_method == "📝 Netlist":
        st.write("Upload or paste SPICE Netlist:")
        netlist_method = st.radio("Method:", ["Upload Netlist file", "Paste text"], horizontal=True)
        if netlist_method == "Upload Netlist file":
            net_file = st.file_uploader("upload file .net or .sp or .txt", type=["net", "sp", "txt"])
            if net_file:
                netlist_content = net_file.read().decode("utf-8")
        elif netlist_method == "Paste text":
            netlist_content = st.text_area("Paste here (SPICE format):", height=200)
    elif input_method == "Use circuit diagram":
        circuit_diagram_html = generate_electrical_schematic_draw()
        with st.expander("🛠️ How to Draw Circuits for Analysis", expanded=False):
            st.components.v1.html(circuit_diagram_html, height=600)
    derivation_steps = st.radio("Derivation Steps:", ["None", "Show derivation steps in markdown format"])
    st.markdown("---")
    derivation_steps_flag = 1 if derivation_steps == "Show derivation steps in markdown format" else 0
    if st.button("Analyze Circuit", use_container_width=True):
            if not img and not netlist_content:
                st.error("Please provide an image, draw a circuit, or input a netlist first.")
            else:
                with st.spinner("Analyzing the circuit..."):
                    st.session_state['project_data']['analysis_request'] = analysis_request
                    st.session_state['project_data']['img'] = img
                    st.session_state['project_data']['netlist_text'] = netlist_content
                    res = analyze_circuit(img, netlist_content, analysis_request, derivation_steps_flag)
                    st.session_state['project_data']['res'] = res

with col_out:
    st.header("2. Circuit Analysis")
    st.info("**Quick Guide:**\n\n"
            "1. **Verify:** Check the formula below matches your circuit diagram.\n"
            "2. **Edit Freely:** All expressions in Desmos can be modified manually.\n"
            "3. **Complex Mode:** For S-domain ($s=j\\omega$), go to Settings (Wrench) -> Enable 'Complex Mode'.\n"
            "4. **Bode Plots:** In Settings -> More Options, switch axes to 'Logarithmic'.\n"
            "5. **Analysis Commands:** Use `|Z|` (Mag), `angle(Z)` (Phase), `real(Z)` (R), and `imag(Z)` (X).\n"
            "6. **Tuning:** Enter values for $g_m, r_o, C$. Delete a parameter's definition to auto-generate a Slider.\n"
            "7. **Note:** Frequency ($f$) is represented by $x$; $s$ is pre-defined as $j 2 \\pi x$.\n"
            "8. **Axis scaling:** To change the scale of the axes, press shift and point to a specific axis, X-axis or Y-axis. Then change the size using the mouse wheel."
            )
    res = st.session_state['project_data'].get('res')
    if not res:
        z_init = """H(s) = 1/(1+R_{e}C_{e}s)"""
        example_img = "LPF.jpg"
        st.image(example_img, caption="Example circuit analysis", width=350)
        R_e = {"name": "R_e", "value": "100", "min": "1", "max": "1000", "step": "10"}
        C_e = {"name": "C_e", "value": "1p", "min": "1f", "max": "10p", "step": "0.1p"}
        calculator_html = generate_calculator_html(z_init, params=[R_e, C_e])
        st.components.v1.html(calculator_html, height=600)
    else:
        res = st.session_state['project_data'].get('res')
        z_latex = res.get('H_latex', '0')
        H_latex_formula = res.get('H_latex_formula', '0')
        topology = res.get('topology', 'Unknown')
        original_params = res.get('params', [])
        params = assign_param_bounds(original_params)
        saved_params = res.get('live_params_values', {})
        if saved_params:
            for i, original_name in enumerate(original_params):
                if original_name in saved_params and str(saved_params[original_name]).strip() != "":
                    params[i]['value'] = str(saved_params[original_name]).strip()
        with st.spinner("Running architecture & topology bug check..."):
            topology = res.get('topology', '')
            formula = res.get('H_latex_formula', '')
            c_uses = st.session_state['project_data'].get('circuit_uses', '')
            bug_res = bug_detector(img, topology, formula, analysis_request, c_uses)
            st.session_state['project_data']['bug_res'] = bug_res
        bug_res = st.session_state['project_data'].get('bug_res')
        if bug_res and bug_res.get("bug_found", "No") == "Yes":
            st.error("⚠️ **Architectural Flaw or Bug Detected!**")
            with st.expander("🚨 View Bug Details & Suggested Fix", expanded=True):
                severity_color = "red" if bug_res.get('severity') in ["High", "Critical"] else "orange" if bug_res.get('severity') == "Medium" else "green"
                st.markdown(f"**Severity:** :{severity_color}[{bug_res.get('severity', 'N/A')}]")
                st.markdown("**Bug Description:**")
                st.write(bug_res.get('bug_description', 'N/A'))
                st.markdown("**Suggested Fix:**")
                st.write(bug_res.get('suggested_fix', 'N/A'))
        opt_res = st.session_state['project_data'].get('opt_res')
        if opt_res:
                    opt_dict = opt_res.get("optimized_parameters", {})
                    for p in params:
                        raw_name = p['name'].replace('_', '').replace('{', '').replace('}', '')
                        new_val = None
                        if p['name'] in opt_dict:
                            new_val = opt_dict[p['name']]
                        elif raw_name in opt_dict:
                            new_val = opt_dict[raw_name]
                        if new_val is not None:
                            p['value'] = str(new_val)
        st.success(f"**Topology:** {res.get('topology')}")
        st.latex(rf"\large {H_latex_formula}")
        st.markdown("---")
        st.info("**Debugging:** Open browser console (F12) to see detailed calculator initialization logs and verify settings are applied correctly.")

        with st.expander("Watch full development"):
            st.write("Analysis process:")
            st.markdown(res.get('derivation_steps', "Not found"))
            st.download_button(
                label="Download text file",
                data=res.get('derivation_steps', ""),
                file_name="circuit_derivation.md",
                mime="text/markdown"
            )
        with st.expander("📚 Reference Formulas (Auto-Detected)"):
            st.markdown("Recognized parameters in the formula: " + ", ".join(res.get('params', [])))
            detected_params = " ".join(res.get('params', [])) + res.get('H_latex_formula', '') + res.get('H_latex', '')
            if 'gm' in detected_params or 'ro' in detected_params or 'M' in detected_params:
                st.markdown("**MOSFET (Saturation Region):**")
                st.latex(r"I_D = \frac{1}{2} \mu C_{ox} \frac{W}{L} (V_{GS} - V_{TH})^2")
                st.latex(r"g_m = \frac{2I_D}{V_{OV}} = \sqrt{2 \mu C_{ox} \frac{W}{L} I_D}")
                st.latex(r"r_o = \frac{1}{\lambda I_D} \approx \frac{V_E L}{I_D}")
                st.divider()
            if 'C' in detected_params:
                st.markdown("**Capacitor:**")
                st.latex(r"Z_C = \frac{1}{sC}")
                st.latex(r"I_C = C \frac{dV_C}{dt}")
                st.divider()
            if 'L' in detected_params:
                st.markdown("**Inductor & LC Tank:**")
                st.latex(r"Z_L = sL")
                st.latex(r"V_L = L \frac{dI_L}{dt}")
                if 'C' in detected_params:
                    st.latex(r"\omega_0 = \frac{1}{\sqrt{LC}} \quad \text{(Resonance Frequency)}")
                st.divider()
            if 'R' in detected_params:
                st.markdown("**Resistor (Thermal Noise):**")
                st.latex(r"\overline{V_n^2} = 4k_B T R \cdot \Delta f")
        calculator_html = generate_calculator_html(st.session_state['project_data']['res'].get('H_latex_formula', '0'), params)
        st.components.v1.html(calculator_html, height=600)
        st.markdown("---")
        st.markdown(
            """
            <style>
            .stTextArea label p {
                font-size: 20px !important;
                font-weight: 600 !important;
            }
            .stTextArea textarea {
                font-size: 18px !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        circuit_uses = st.text_area("Describe the use cases of the circuit (for example: low noise amplifier for 1GHz, power amplifier for 100MHz etc.):", height=150)
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("AI Circuit Advisor"):
                if not img:
                    st.error("please upload something")
                else:
                    with st.spinner("Analyzing circuit use cases..."):
                        st.session_state['project_data']['circuit_uses'] = circuit_uses 
                        st.session_state['project_data']['advisor_res'] = electrical_advisor(img, topology, analysis_request, circuit_uses)
        with col_btn2:
                    if st.button("⚡ Optimize Parameters", use_container_width=True):
                        opt_result = optimize_circuit(params, img, H_latex_formula, analysis_request, circuit_uses)
                        if opt_result:
                            st.session_state['project_data']['opt_res'] = opt_result
                            st.success("Optimization complete! Updating calculator...")
                            st.rerun()
        render_feedback_section(st.session_state['project_data'])
        with st.expander("🔧 Debugging Information"):
                    st.markdown("""
                    **To debug the calculator:**
                    1. Open browser Developer Tools (F12)
                    2. Go to the Console tab
                    3. Look for initialization messages starting with "Initializing Desmos Calculator..."
                    4. Check if settings are applied successfully
                    5. Use `window.desmosCalc` in console to access the calculator object directly
                    
                    **Common issues:**
                    - Settings not applied: Check console for error messages
                    - Graph not displaying correctly: Verify complex mode is enabled
                    - Axis issues: Check if log mode settings were applied
                    """)
                    st.markdown("---")
                    st.markdown("### 🧠 Live System Memory (`project_data`)")
                    debug_dict = {}
                    for key, value in st.session_state['project_data'].items():
                        if key == 'img':
                            debug_dict[key] = "🖼️ [Image Object]" if value is not None else None
                        else:
                            debug_dict[key] = value
                            z_latex = value
                    st.json(debug_dict)
                    st.json(z_latex)
        if st.session_state['project_data'].get('opt_res'):
            opt = st.session_state['project_data']['opt_res']
            with st.expander("⚡ Optimization Results & Advice", expanded=True):
                st.markdown("**New Optimized Parameters:**")
                st.json(opt.get("optimized_parameters", {}))
                st.markdown("**Advice / Reasoning:**")
                st.write(opt.get("optimization_advice", "No advice provided."))
        if st.session_state['project_data'].get('advisor_res'):
            adv = st.session_state['project_data']['advisor_res']
            with st.expander("AI Electrical Advisor - Detailed Recommendations and Derivation", expanded=True):
                st.markdown("**Performance Advice:**")
                st.markdown(adv.get('performance_advice', "Not found"))
                st.markdown("**Power Advice:**")
                st.markdown(adv.get('power_advice', "Not found"))
                st.markdown("**Noise Advice:**")
                st.markdown(adv.get('noise_advice', "Not found"))
                st.markdown("**Component Advice:**")
                st.markdown(adv.get('component_advice', "Not found"))
                st.markdown("**Recommended Articles:**")
                st.markdown(adv.get('Recommended_articles_links', "Not found"))
    render_save_project_section(st.session_state['project_data'])

show_guidde_video()
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
with st.sidebar:
    st.header("Analog/RF Expert Copilot")
    st.markdown("Ask me anything about the current circuit, layout considerations, or RF matching.")
    st.divider()
    for message in st.session_state['chat_history']:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("Ask a question (e.g., 'How to improve the phase margin?')..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        current_context = ""
        if st.session_state.get('res'):
            res = st.session_state['res']
            current_context = f"""
            Current Circuit Context:
            - Topology: {res.get('topology', 'Unknown')}
            - Derived Equation: {res.get('H_latex_formula', 'Unknown')}
            - Analysis Request: {analysis_request}
            - Use Cases: {circuit_uses if circuit_uses else 'Not specified'}
            """
        sys_prompt = f"""
        You are a Senior Analog and RF IC Design Engineer.
        Your job is to assist the user with circuit design, small-signal analysis, noise, power optimization, and RF matching.
        Keep your answers professional, highly technical, and concise. Use standard VLSI terminology.
        {current_context}
        """
        chat_model = genai.GenerativeModel('gemini-2.5-pro',system_instruction=sys_prompt)
        gemini_history = [
            {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]} 
            for msg in st.session_state['chat_history']
        ]
        chat = chat_model.start_chat(history=gemini_history)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    img_for_chat = st.session_state['project_data'].get('img')
                    if img_for_chat is not None and len(st.session_state['chat_history']) == 0:
                        response = chat.send_message([prompt, img_for_chat])
                    else:
                         response = chat.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state['chat_history'].append({"role": "user", "content": prompt})
                    st.session_state['chat_history'].append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Chat error: {e}")



