import streamlit as st
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
from GUI import col_in, col_out, set_page_config

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

col_in, col_out = st.columns([1, 2])

GUI.set_page_config()
GUI.col_in()
GUI.col_out()
