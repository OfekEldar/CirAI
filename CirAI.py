import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_paste_button import paste_image_button
import json
import re
import base64
import os

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
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

def generate_calculator_html(z_latex):
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
    html_content = html_content.replace('{z_latex}', z_latex)
    
    return html_content

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
        "Recommended_articles_links": "Recommendation for articles related to the circuit, similar circuits, similar architectures, etc. give a links to the articles in this format: "Article 1, Article 2, Article 3, ... " 
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

def assign_param_bounds(param_list):
    bounds_config = {
        'gm': (1e-3, 500e-3),
        'R':  (1, 1000),
        'C':  (1e-15, 10e-12),
        'L':  (50e-12, 500e-12),
        'ro': (1,10000),
        'A': (0.1,100000)
    }  
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
        elif name.startswith('ro'):
            min_val, max_val = bounds_config['ro']
        elif name.startswith('A'):
            min_val, max_val = bounds_config['A']    
        else:
            print(f"Warning: Unknown parameter type for '{name}'")
            continue 
        result.append([name, min_val, max_val])
    return result

# --- GUI ---
st.set_page_config(page_title="Analog Design Pro", layout="wide")
st.title("CirAI:Electrical circuit Image or netlist to Interactive Math")

if 'res' not in st.session_state:
    st.session_state['res'] = None
if 'advisor_res' not in st.session_state:
    st.session_state['advisor_res'] = None
col_in, col_out = st.columns([1, 2])

with col_in:
    st.header("1. Input (Image or Netlist)")
    uploaded_file = st.file_uploader("Upload circuit image", type=["png", "jpg", "jpeg"])
    paste_result = paste_image_button(label="Paste here", errors="ignore")
    netlist_file = st.file_uploader("Upload circuit Netlist", type=["txt"])
    analysis_request = st.text_input("Function to analyze (for example: Vout/Vin, Z(Vout) etc.):", value="Vout")
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="The analyzed circuit", width=350)
    else:
        img = None
    if paste_result.image_data is not None:
        st.write("Image pasted")
        st.image(paste_result.image_data)
        img = paste_result.image_data
    st.markdown("---")
    netlist_method = st.radio("Netlist:", ["None", "Upload Netlist file", "Paste text"])
    netlist_content = None
    if netlist_method == "Upload Netlist file":
        net_file = st.file_uploader("upload file .net or .sp or .txt", type=["net", "sp", "txt"])
        if net_file:
            netlist_content = net_file.read().decode("utf-8")
    elif netlist_method == "Paste text":
        netlist_content = st.text_area("Paste here(SPICE format):", height=150)
    derivation_steps = st.radio("Derivation Steps:", ["None", "Show derivation steps in markdown format"])
    if derivation_steps == "Show derivation steps in markdown format":
        derivation_steps_flag = 1
    if st.button("GO"):
        if not img and not netlist_content:
            st.error("please upload something")
        else:
            with st.spinner("Analyze..."):
                st.session_state['res'] = analyze_circuit(img, netlist_content, analysis_request, derivation_steps_flag)

with col_out:
    st.header("2. Circuit Analysis")
    st.info("**Quick Guide:**\n\n"
            "1. **Verify:** Check the formula below matches your circuit diagram.\n"
            "2. **Edit Freely:** All expressions in Desmos can be modified manually.\n"
            "3. **Complex Mode:** For S-domain ($s=j\\omega$), go to Settings (Wrench) -> Enable 'Complex Mode'.\n"
            "4. **Bode Plots:** In Settings -> More Options, switch axes to 'Logarithmic'.\n"
            "5. **Analysis Commands:** Use `|Z|` (Mag), `angle(Z)` (Phase), `real(Z)` (R), and `imag(Z)` (X).\n"
            "6. **Tuning:** Enter values for $g_m, r_o, C$. Delete a parameter's definition to auto-generate a Slider.\n"
            "7. **Note:** Frequency ($f$) is represented by $x$; $s$ is pre-defined as $j 2 \\pi x$.")
    if st.session_state['res'] == None:
        z_init = 'Z(s) = 0'  # Default initial expression
        example_img = "LPF.jpg"
        st.image(example_img, caption="Example circuit analysis", width=350)
        calculator_html = generate_calculator_html(z_init)
        st.components.v1.html(calculator_html, height=600)
    elif st.session_state['res']:
        res = st.session_state['res']
        z_latex = res.get('H_latex', '0')
        H_latex_formula = res.get('H_latex_formula', '0')
        topology = res.get('topology', 'Unknown')
        print(z_latex)
        st.success(f"**Topology:** {res.get('topology')}")
        st.latex(rf"\large {H_latex_formula}")
        st.markdown("---")
        st.info("**Debugging:** Open browser console (F12) to see detailed calculator initialization logs and verify settings are applied correctly.")
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
        with st.expander("Watch full development"):
            st.write("Analysis process:")
            st.markdown(res.get('derivation_steps', "Not found"))
            st.download_button(
                label="Download text file",
                data=res.get('derivation_steps', ""),
                file_name="circuit_derivation.md",
                mime="text/markdown"
            )
        # Generate calculator HTML using template
        calculator_html = generate_calculator_html(z_latex)
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
        if st.button("AI Circuit Advisor"):
            if not img:
                st.error("please upload something")
            else:
                with st.spinner("Analyzing circuit use cases..."):
                    st.session_state['advisor_res'] = electrical_advisor(img, topology, analysis_request, circuit_uses)
        if st.session_state['advisor_res']:
            adv = st.session_state['advisor_res']
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
    else:
        st.info("Upload image or netlist to start")

# --- Analog/RF Expert Chatbot (Sidebar) ---
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
            """
        sys_prompt = f"""
        You are a Senior Analog and RF IC Design Engineer.
        Your job is to assist the user with circuit design, small-signal analysis, noise, power optimization, and RF matching.
        Keep your answers professional, highly technical, and concise. Use standard VLSI terminology.
        {current_context}
        """
        chat_model = genai.GenerativeModel(
            'gemini-2.5-pro',
            system_instruction=sys_prompt
        )
        gemini_history = [
            {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]} 
            for msg in st.session_state['chat_history']
        ]
        chat = chat_model.start_chat(history=gemini_history)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if 'img' in st.session_state and st.session_state['img'] is not None and len(st.session_state['chat_history']) == 0:
                         response = chat.send_message([prompt, st.session_state['img']])
                    else:
                         response = chat.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state['chat_history'].append({"role": "user", "content": prompt})
                    st.session_state['chat_history'].append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Chat error: {e}")



