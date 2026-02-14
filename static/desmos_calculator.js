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
    yAxisScale: 'linear'
};

const DEFAULT_BOUNDS = {
    left: 10000,
    right: 10000000000,
    bottom: -2,
    top: 2
};

// Unit definitions for engineering notation
const UNIT_DEFINITIONS = [
    {id: 'f_unit', latex: 'f = 10^{-15}'},
    {id: 'p_unit', latex: 'p = 10^{-12}'},
    {id: 'n_unit', latex: 'n = 10^{-9}'},
    {id: 'u_unit', latex: 'u = 10^{-6}'},
    {id: 'm_unit', latex: 'm = 10^{-3}'},
    {id: 'k_unit', latex: 'k = 10^{3}'},
    {id: 'M_unit', latex: 'M = 10^{6}'},
    {id: 'G_unit', latex: 'G = 10^{9}'}
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

    /**
     * Initialize the calculator
     */
    init() {
        console.log('Initializing Desmos Calculator...');
        
        const element = document.getElementById(this.elementId);
        if (!element) {
            console.error(`Element with ID '${this.elementId}' not found`);
            return;
        }

        this.calculator = Desmos.GraphingCalculator(element, CALCULATOR_CONFIG);
        
        // Make calculator available globally for debugging
        window.desmosCalc = this.calculator;
        console.log('Calculator object available as window.desmosCalc for debugging');

        // Apply settings after initialization
        this.applySettings();
    }

    /**
     * Apply calculator settings with error handling
     */
    applySettings() {
        setTimeout(() => {
            console.log('Applying calculator settings...');
            
            try {
                // Apply all settings in a single call
                this.calculator.updateSettings(DEFAULT_SETTINGS);
                
                // Set math bounds
                this.calculator.setMathBounds(DEFAULT_BOUNDS);
                console.log(`setMathBounds called with bounds: left=${DEFAULT_BOUNDS.left}, right=${DEFAULT_BOUNDS.right}, bottom=${DEFAULT_BOUNDS.bottom}, top=${DEFAULT_BOUNDS.top}`);
                
                this.logSettingsStatus();
                this.isReady = true;
                window.calculatorReady = true;
                
            } catch (error) {
                console.error('Error applying settings:', error);
                this.applySettingsIndividually();
            }
            
            // Add expressions after settings
            this.addExpressions();
            
        }, 500);
    }

    /**
     * Apply settings individually for debugging
     */
    applySettingsIndividually() {
        const settingsToTry = [
            {setting: {degreeMode: false}, name: 'Degree mode'},
            {setting: {xAxisScale: 'logarithmic'}, name: 'X-axis logarithmic scale'}
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
            {id: 'f', latex: 'Z = \\frac{1}{1+sR_{e}C_{e}}'},
            {id: 'slider1', latex: 'R_{e}=100', sliderBounds: {min: 100,max: 100000000,step: 1}},
            {id: 'slider2', latex: 'C_{e} = 1p'},
            /*{id: 'z_val', latex: `Z = ${this.zLatex}`},*/
            {id: 'z_abs', latex: '\\left|Z\\right|'},
            {id: 'z_phase', latex: '\\arctan\\left(\\frac{\\operatorname{imag}\\left(Z\\right)}{\\operatorname{real}\\left(Z\\right)}\\right)'},
            {id: 's_def', latex: 's = i * 2 * \\pi * x'}
        ];

        coreExpressions.forEach(expr => {
            this.calculator.setExpression(expr);
        });
    }

    /**
     * Add engineering unit definitions
     */
    addUnitDefinitions() {
        UNIT_DEFINITIONS.forEach((unit, index) => {
            try {
                this.calculator.setExpression(unit);
                console.log(`Unit ${index + 1} added successfully`);
            } catch (e) {
                console.error(`Unit ${index + 1} failed:`, e);
            }
        });
    }

    /**
     * Get calculator status
     */
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