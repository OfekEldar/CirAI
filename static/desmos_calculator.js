/**
 * Desmos Calculator Configuration and Initialization
 */

// Configuration Constants
const CALCULATOR_CONFIG = {
    allowComplex: true,
    expressions: true,
    settingsMenu: true,
    smartGrapher: true
};

const DEFAULT_SETTINGS = {
    degreeMode: false,
    xAxisScale: 'logarithmic',
    yAxisScale: 'linear',
    xAxisLabel: 'Frequency [Hz]',
    yAxisLabel: 'Magnitude \ Phase'
};

const DEFAULT_BOUNDS = {
    left: 10000,
    right: 10000000000,
    bottom: -2,
    top: 2
};

// Unit definitions for engineering notation
const UNIT_DEFINITIONS = [
    {id: 'units',type: 'folder',title: 'Units'},
    {id: 'f_unit', latex: 'f = 10^{-15}', folderId: 'units'},
    {id: 'p_unit', latex: 'p = 10^{-12}', folderId: 'units'},
    {id: 'n_unit', latex: 'n = 10^{-9}', folderId: 'units'},
    {id: 'u_unit', latex: 'u = 10^{-6}', folderId: 'units'},
    {id: 'm_unit', latex: 'm = 10^{-3}', folderId: 'units'},
    {id: 'k_unit', latex: 'k = 10^{3}', folderId: 'units'},
    {id: 'M_unit', latex: 'M = 10^{6}', folderId: 'units'},
    {id: 'G_unit', latex: 'G = 10^{9}', folderId: 'units'}
];

/**
 * Calculator Management Class
 */
class DesmosCalculatorManager {
    constructor(elementId, zLatex) {
        this.elementId = elementId;
        this.zLatex = zLatex;
        this.calculator = null;
        this.isReady = false;
        this.isFullyReady = false;
    }

    init() {
        console.log('Initializing Desmos Calculator...');
        const element = document.getElementById(this.elementId);
        if (!element) {
            console.error(`Element with ID '${this.elementId}' not found`);
            return;
        }
        this.calculator = Desmos.GraphingCalculator(element, CALCULATOR_CONFIG);
        let state = this.calculator.getState();
        if (!state.graph) state.graph = {};
        state.graph.complexMode = true;
        this.calculator.setState(state);
        window.desmosCalc = this.calculator;
        console.log('Calculator object available as window.desmosCalc for debugging');
        this.applySettings();
    }
    applySettings() {
        setTimeout(() => {
            console.log('Applying calculator settings...'); 
            try {
                this.calculator.updateSettings(DEFAULT_SETTINGS);
                this.calculator.setMathBounds(DEFAULT_BOUNDS);
                console.log(`setMathBounds called with bounds: left=${DEFAULT_BOUNDS.left}, right=${DEFAULT_BOUNDS.right}, bottom=${DEFAULT_BOUNDS.bottom}, top=${DEFAULT_BOUNDS.top}`);
                this.logSettingsStatus();
                this.isReady = true;
                window.calculatorReady = true;  
            } catch (error) {
                console.error('Error applying settings:', error);
                this.applySettingsIndividually();
            }
            this.addExpressions();
        }, 500);
    }

    /**
     * Apply settings individually for debugging
     */
    applySettingsIndividually() {
        const settingsToTry = [
            {setting: {degreeMode: false}, name: 'Degree mode'},
            {setting: {xAxisScale: 'logarithmic'}, name: 'X-axis logarithmic scale'},
            {setting: {xAxisLabel: 'Frequency [Hz]'}, name: 'X-axis logarithmic scale'}
        ];

        settingsToTry.forEach(({setting, name}) => {
            try {
                this.calculator.updateSettings(setting);
                console.log(`${name} applied successfully`);
            } catch (e) {
                console.error(`${name} failed:`, e);
            }
        });

        try {
            this.calculator.setMathBounds(DEFAULT_BOUNDS);
            console.log('Math bounds applied successfully');
        } catch (e) {
            console.error('Math bounds failed:', e);
        }
    }

    /**
     * Log current settings status
     */
    logSettingsStatus() {
        console.log('Settings applied successfully!');
        console.log('Degree Mode:', this.calculator.settings.degreeMode);
        console.log('X Axis Scale:', this.calculator.settings.xAxisScale);
        console.log('Y Axis Scale:', this.calculator.settings.yAxisScale);
        console.log(`Math bounds should now be: left=${DEFAULT_BOUNDS.left}, right=${DEFAULT_BOUNDS.right}, bottom=${DEFAULT_BOUNDS.bottom}, top=${DEFAULT_BOUNDS.top}`);
    }

    /**
     * Add expressions to the calculator
     */
    addExpressions() {
        setTimeout(() => {
            console.log('Adding expressions...');
            
            try {
                // Core expressions
                this.addCoreExpressions();
                
                // Unit definitions
                this.addUnitDefinitions();
                
                console.log('All expressions added successfully!');
                this.isFullyReady = true;
                window.calculatorFullyReady = true;
                
            } catch (error) {
                console.error('Error adding expressions:', error);
            }
        }, 200);
    }

    /**
     * Add core mathematical expressions
     */
    addCoreExpressions() {
        const coreExpressions = [
            {id: 'expressions', type: 'folder', title: 'Expressions'},
            {id: 'params', type: 'folder', title: 'Params'},
            {id: 'Z', latex: '{z_latex}', folderId: 'expressions'},
            {id: 'f', latex: 'f_{z} = \\frac{1}{1+sR_{e}C_{e}}'},
            {id: 'slider1', latex: 'R_{e}=100', sliderBounds: {min: 100000,max: 1000000,step: 1}, folderId: 'params'},
            {id: 'slider2', latex: 'C_{e} = 1p', folderId: 'params'},
            /*{id: 'z_val', latex: `Z = ${this.zLatex}`},*/
            {id: 'H_abs', latex: '\\left|H(s)\\right|', folderId: 'expressions'},
            {id: 'H_phase', latex: '-90-\\frac{180}{\\pi}\\cdot\\arctan\\left(\\operatorname{real}\\left(H\\left(s\\right)\\right),\\operatorname{imag}\\left(H\\left(s\\right)\\right)\\right)', folderId: 'expressions'},
            {id: 'z_abs', latex: '\\left|f_{z}\\right|', folderId: 'expressions'},
            {id: 'z_phase', latex: '\\arctan\\left(\\frac{\\operatorname{imag}\\left(f_{z}\\right)}{\\operatorname{real}\\left(f_{z}\\right)}\\right)', folderId: 'expressions'},
            {id: 's_def', latex: 's = i * 2 * \\pi * x', folderId: 'expressions'}
        ];

        coreExpressions.forEach(expr => {
            this.calculator.setExpression(expr);
        });
    }
    addUnitDefinitions() {
        UNIT_DEFINITIONS.forEach((unit, index) => {
            try {
                this.calculator.setExpression(unit);
                console.log(`Unit ${index + 1} added successfully`);
            } catch (e) {
                console.error(`Unit ${index + 1} failed:`, e);
            }
        });
        let state = calculator.getState();
        state.expressions.list = state.expressions.list.concat(UNIT_DEFINITIONS);
        calculator.setState(state);
    }


    getStatus() {
        return {
            isReady: this.isReady,
            isFullyReady: this.isFullyReady,
            calculator: this.calculator
        };
    }
}

function initializeCalculator(zLatex) {
    const manager = new DesmosCalculatorManager('calculator', zLatex);
    manager.init();
    return manager;

}



