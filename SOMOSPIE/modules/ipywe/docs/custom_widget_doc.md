# How to Make a Custom Widget for the Jupyter Notebook

## Introduction to the Custom Widget Framework

* Consists of a Python (or similar language) backend and a Javascript frontend
* This backend-frontend format for the widget allows the widget to work on an MVC system.
    * The Python code controlls the widget and widget model (M).
    * The Javascript code controlls the widget view (V and C).
* By convention, the frontend should contain most of the code.
    * The only things the backend must do are:
    * Be a subclass of the Widgets and DOMWidgets classes (DOMWidgets is a subclass of Widgets)
    * Contain the variables that will be synced between the front- and back- ends

## Backend:

### Connecting the Front- and Back-ends: Backend Requirements
* To sync to two ends of the widget, the backend requires two variables to be initialized and synced with the frontend:
    * `_view_name`: the name of the view
    * `_view_module`: the module name for the view (_**not** required for full distribution packaging_)
* There are also two *optional* variables that can be initialized and synced to explicitly define the model:
    * `_model_name`: the name of the model (_required for full distribution packaging_)
    * `_model_module`: the module name for the model
* All of these variables are initialized and synced with the same syntax:
    ```
    (_view_name/_view_module/_model_name/_model_module) = Unicode(Value).tag(sync=True)
    ```
    * *Value*: the string that the variable is set to
* If the code is part of a full distribution package, an ipywidgets.register decorator must be added before the start fo the class. The decorator syntax is as follows:
    ```
    @ipywidgets.register(ipywidgets.className)
    class className
    ```

### Syncing Variables:
* Requires the traitlets module (or the individual traits from this module) to be imported
* Syncing variables should be the first thing done in the widget's Python class
    * `_view_name`, `_view_module`, `_model_name`, and/or `_model_module` should be first
* Syntax for Syncing Variables:
    ```
    Variable_Name = traitlets.Trait_Type.(Initial_Trait_Value).tag(sync=True)
    ```
    * *Variable_Name*: the name of the variable being synced
    * *Trait_Type*: the trait with which *Variable_Name* is being set
    * *Inital_Trait_Value*: the value that *Variable_Name* is being set to. This is optional.

### Adding a Custom Construction (*Optional*)
* By default, the `__init__` constructor is entirely inherited from the DOMWidgets class.
* To override the contructor, the following statement must be placed at the end of the custom `__init__` function:
    ```
    super(Widget_Class_Name, self).__init__()
    ```
    * *Widget_Class_Name*: the name of the widget's Python class

### Other Functions (*Optional*)
* Added to the backend in the same way that they would be for any other Python program
* Because the controller is in the frontend, actions/events __cannot__ directly call these functions.
    * To trigger these functions, observe statements that track one or more synced variables should be used.
    * The tag-style (decorator) observe statement should be used.
    * Requires __HasTraits__ and __observe__ to be imported from __traitlets__.
    * Decorator Syntax for the observe statement (must be on the line before the function starts):
       ```
       @observe(Observed_Variable(s))
       ```

## Frontend

### Connecting the Front- and Back-ends: Frontend Requirements
* To sync the front- and back-ends, the frontend must be setup with the following format:
   ``` 
   define(_view_module_Value,["jupyter-js-widgets"],function(widgets){
       var _view_name_Value = widgets.DOMWidgetView.extend({
           render: function() {
               Code for Render Function
           },
           Other Functions (Optional)
        });

        return {
            _view_name_Value : _view_name_Value
        };
    });
    ```
    * *_view_module Value*: the value of the `_view_module` variable (set on the backend)
    * *_view_name Value*: the value of the `_view_name` variable (set on the backend)
    * The only functions that must be included are:
        * The function that begins in the define statement
        * The render function
    * By convention, all other functions should be used for events.
    * Note that this does __not__ apply for code in a full distribution package. For an example of the format for a full distribution file, see <https://github.com/neutrons/ipywe/blob/master/js/src/imgdisplay.js>.

### The Render Function
* Essentially, the "main" function of the frontend.
* Should contain all the code that changes the DOM, including:
    * Creating DOM Elements (i.e. Images, Sliders, etc.)
    * Changing element attributes or properties (i.e. class, id, src, style, etc.)
    * Adding elements to the current DOM element with *this.$el*
* This is where all events should be handled.

### Events
* DOM Events:
    * Triggered by mouse/keyboard input
    * Handled by a standard Javascript event handler system (i.e. HTML DOM Event Objects, jQuery, etc.)
* Model Change Events:
    * Triggered by changes to the values of synced variables
    * Uses the `this.model.on("change:`*variable to track*`,this.`*function to be triggered*`,this)` function
        * *Variable to Track*: the name of the variable being tracked by the event
        * *Function to be Triggered*: the name of the Javascript function that will be triggered when *Variable to Track* changes

### Getting the Value of Synced Variables
* Use the `this.model.get()` function:
    * This function takes 1 parameter:
        * A string containing the name of the variable whose value you want to get.
    * This function returns the value of the specified variable.

### Setting the Value of a Synced Variables
* Setting the value of a synced variable is a two-step process
    * First, call the `this.model.set()` function.
        * This function takes 2 parameters:
            * A string containing the name of the variable whose value you want to change
            * The value that you want to set the variable to
    * Then, to actually change the variable's value on the backend, call the `this.touch()` function.
    * This function takes no parameters and returns nothing.

### The Return Statement
* What allows the widget to be rendered on-screen
* Always contains two copies of the value of `_view_name` seperated by a comma.
* It should never contain anything else.
* Again, this only applies if the file is __not__ going to be in a full distribution package.

## Packaging the Widget

### Packaging as a Single File
* To keep all the widget's code in a single file, add a new function outside of the widget's class in the Python code.
    * This function contains a single call to the `set_ipython().run_cell_magic()` function
        * This function can only be run inside a Jupyter notebook.
        * It accepts 3 parameters (all strings):
            * The type of magic that would be used in a Jupyter notebook (for these widgets, this should always be *'javascript'*)
            * The external file that is being used (this should be empty if the magic is not something like "writefile")
            * The code to be run (for a widget, this should be the frontend Javascript code __that contains appropriate string formatting__
* This function should either be called in the widget's constructor (if it was overridden) or in the notebook before the widget constructor is called.

### Packaging as Two Files
* Create a .py file for the Python code and a .js file for the Javascript code
* Inside the .py file, create two new functions outside the widget's class:
    * Function 1: Read the Javascript file into a variable (using `open().read()`) and return that variable (with the appropriate encoding)
    * Function 2: Run the Javascript code using one of two methods:
        * Import __display__ and __HTML__ from __IPython.display__ and enter `display(HTML("<script>" +` *Javascript* `+ "</script>"))`
            * *Javascript*: the variable that stores the result that was returned from Function 1
        * Use the `get_ipython().run_cell_magic()` function (see above) with the third parameter being the result of Function 1

### Full Distribution Packaging
* To make a Custom Widget fully distributable through pip and npm, use the [IPyWidgets Cookiecutter template](https://github.com/jupyter-widgets/widget-cookiecutter "Cookiecutter Homepage").
* An example of this type of packaging can be found at <https://github.com/neutrons/ipywe>.

## Displaying the Widget
* For full distribution packaging, ensure the distribution has been downloaded through pip or npm (the widget's GitHub page will have download instructions).
* Import the widget's (Python) file/distribution as you would any other module
* Create an instance of the widget using the widget's constructor
* Type the name of the widget instance (or just the constructor) and run the code block that this instance is in to display the widget.

## Tips
1. Develop the widget in its own Jupyter notebook, especially if you will package the widget in a single file.
    * This allows you to quickly run both the Python and Javascript code without messing around with packaging.
    * For single-file packaging, you can use Jupyter to convert the notebook into a .py file. This file will contain the correct implementation of the `get_ipython().run_cell_magic()` function (including the correct string formatting for the Javascript code).
2. It is highly recommended that you use jQuery in your Javascript code to simplify looking up DOM elements.
3. In the backend *observe* statements, you should try to use variables that are used for calculations as much as possible. For very large widgets, having a large number of synced variables that do nothing but trigger functions could slow the widget down.

## More Information
* For general documentation on Custom Jupyter Widgets, visit <http://ipywidgets.readthedocs.io/en/latest/examples/Widget%20Custom.html>
* For low-level documentation on Custom Widgets (including a detailed description of how the MVC framework is created by the code), visit <http://ipywidgets.readthedocs.io/en/latest/examples/Widget%20Low%20Level.html>
* For practical examples of Custom Widgets, visit <https://github.com/neutrons/ipywe/tree/master/ipywe> (Note that the __fileselector__ and __wizard__ widgets do not run on this framework).
