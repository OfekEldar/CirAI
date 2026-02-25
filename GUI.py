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
# --- GUI ---

def set_page_config():
    st.set_page_config(page_title="Analog Design Pro", layout="wide")
    st.set_page_config(page_title="Analog Design Pro", layout="wide")
    st.title("CirAI:Electrical circuit Image or netlist to Interactive Math")
    if 'res' not in st.session_state:
        st.session_state['res'] = None
    if 'advisor_res' not in st.session_state:
        st.session_state['advisor_res'] = None

def col_in():
    with col_in:
        st.header("1. Input (Image or Netlist)")
        analysis_request = st.text_input("Function to analyze (for example: Vout/Vin, Z(Vout) etc.):", value="Vout")
        input_method = st.radio(
            "Select Input Method:", 
            ["🖼️ Upload / Paste", "✏️ Draw Circuit", "📝 Netlist"], 
            horizontal=True
        )
        img = None
        netlist_content = None
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
        elif input_method == "✏️ Draw Circuit":
                st.write("Draw your schematic directly (use standard symbols):")
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
                canvas_result = st_canvas(
                    fill_color="rgba(255, 165, 0, 0.3)",
                    stroke_width=stroke_width,
                    stroke_color=color, 
                    background_color="#ffffff", 
                    height=400,
                    width=400,
                    drawing_mode=mode,
                    key="circuit_canvas",
                )
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
        derivation_steps = st.radio("Derivation Steps:", ["None", "Show derivation steps in markdown format"])
        st.markdown("---")
        derivation_steps_flag = 1 if derivation_steps == "Show derivation steps in markdown format" else 0
        if st.button("Analyze Circuit", use_container_width=True):
            if not img and not netlist_content:
                st.error("Please provide an image, draw a circuit, or input a netlist first.")
            else:
                with st.spinner("Analyzing the circuit..."):
                    st.session_state['res'] = analyze_circuit(img, netlist_content, analysis_request, derivation_steps_flag)
                    st.session_state['img'] = img
        show_guidde_video()
def col_out():
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
                        if 'img' in st.session_state and st.session_state['img'] is not None and len(st.session_state['chat_history']) == 0:
                            response = chat.send_message([prompt, st.session_state['img']])
                        else:
                            response = chat.send_message(prompt)
                        st.markdown(response.text)
                        st.session_state['chat_history'].append({"role": "user", "content": prompt})
                        st.session_state['chat_history'].append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Chat error: {e}")



