import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import re

# --- הגדרות API ---
# הערה: המפתח שלך מופיע פה, וודא שהוא פעיל ב-Google AI Studio
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)

def analyze_circuit(image, target_node):
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = """
    You are an expert Analog IC Design Engineer.
    Extract the symbolic Zout formula for the given node.
    Include all elements (R, L, C).
    Include active elements (nmos, pmos etc.) model it by small signal model (current source and ro).
    Output ONLY a valid JSON object:
    {
      "topology": "Topology Name",
      "z_latex_formula": "formula using s, R, C, L, g_m, r_o in regular LaTex format, The expression should be as simplified as possible. Do not use the || (parallel) symbol, but simplify the equation as much as possible. do not neglect any parameter",
      "zout_latex": "formula using s, R, C, L, g_m, r_o. use the Desmos calculator LaTex format only. for example: {5+a_{2}}/{s^{2}+\\\\pi*s-{1}/{5*s}}. use * for multiply, / for divition. any nominator or denominator, put in parentheses: '()'"
    }
    """
    response = model.generate_content([prompt, image, f"Node: {target_node}"])
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None

# --- GUI ---
st.set_page_config(page_title="Analog Design Pro", layout="wide")
st.title("🛠️ Analog Design Tool: Image to Interactive Math")

if 'res' not in st.session_state:
    st.session_state['res'] = None

col_in, col_out = st.columns([1, 1.2])

with col_in:
    st.header("1. קלט")
    uploaded_file = st.file_uploader("העלה תמונה", type=["png", "jpg", "jpeg"])
    target_node = st.text_input("צומת מטרה (למשל Vout):", value="Vout")
    if uploaded_file:
        img = Image.open(uploaded_file)
        # הגבלת גודל תמונה כפי שביקשת קודם
        st.image(img, caption="המעגל המנותח", width=350)
    if st.button("נתח מעגל"):
        with st.spinner("Analyze..."):
            st.session_state['res'] = analyze_circuit(img, target_node)

with col_out:
    st.header("2. ניתוח אינטראקטיבי")
    st.info("**Quick Guide:**\n\n"
            "1. **Verify:** Check the formula below matches your circuit diagram.\n"
            "2. **Edit Freely:** All expressions in Desmos can be modified manually.\n"
            "3. **Complex Mode:** For S-domain ($s=j\omega$), go to Settings (Wrench) -> Enable 'Complex Mode'.\n"
            "4. **Bode Plots:** In Settings -> More Options, switch axes to 'Logarithmic'.\n"
            "5. **Analysis Commands:** Use `|Z|` (Mag), `angle(Z)` (Phase), `real(Z)` (R), and `imag(Z)` (X).\n"
            "6. **Tuning:** Enter values for $g_m, r_o, C$. Delete a parameter's definition to auto-generate a Slider.\n"
            "7. **Note:** Frequency ($f$) is represented by $x$; $s$ is pre-defined as $j 2 \pi x$.")
    if st.session_state['res']:
        res = st.session_state['res']
        z_latex = res.get('zout_latex', '0')
        z_latex_formula = res.get('z_latex_formula', '0')
        print(z_latex)
        st.success(f"**Topology:** {res.get('topology')}")
        st.latex(f"Z(s) = {z_latex_formula}")
        

# --- תיקון לוגיקת Desmos ---
        desmos_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; }}
                        #calculator {{ width: 100%; height: 500px; }}
                    </style>
                    <script src="https://www.desmos.com/api/v1.11/calculator.js?apiKey=27dbc719129a4adab82767f98e6fc813"></script>
                </head>
                <body>
                    <div id="calculator"></div>
                    <script>
                        var z_from_python = "{z_latex}";
                        
                        // וודא שהאלמנט קיים
                        var elt = document.getElementById('calculator');
                        
                        // 1. יצירת המחשבון עם Configuration Options
                        var calculator = Desmos.GraphingCalculator(elt, {{
                            allowComplex: true,
                            expressions: true,
                            settingsMenu: true,
                            smartGrapher: true
                        }});

                        // 2. הגדרת Graph Settings (מצב מרוכב ורדיאנים)
                        calculator.updateSettings({{
                            complexMode: true,
                            degreeMode: false
                        }});

                        // 3. הזנת ביטויים - שים לב לשימוש ב-IDs שונים
                        calculator.setExpression({{ id: 'j_def', latex: 'j=i' }});
                        
                        // הגדרת משתנה תדר s על ציר ה-x
                        calculator.setExpression({{ id: 's_def', latex: 's = i * 2 * \\\\pi * x' }});
                        calculator.setExpression({{ id: 'z_val', latex: 'Z = ' + z_from_python }});
                        calculator.setExpression({{ 
                            id: 'real_z', 
                            latex: '\\\real(Z)',
                            color: Desmos.Colors.BLUE 
                        }});
                    </script>
                </body>
                </html>
                """
        st.components.v1.html(desmos_html, height=550)
    else:
        st.info("העלה תמונה ולחץ על 'נתח מעגל' כדי להתחיל.")