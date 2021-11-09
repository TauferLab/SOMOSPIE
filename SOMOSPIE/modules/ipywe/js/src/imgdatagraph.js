var widgets = require('jupyter-js-widgets');
var _ = require('underscore');
var semver_range = "^" + require("../package.json").version;

var ImgDataGraphModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(_.result(this, 'widgets.DOMWidgetModel.prototype.defaults'), {
        _model_name : 'ImgDataGraphModel',
        _view_name : 'ImgDataGraphView',
        _model_module : 'ipywe',
        _view_module : 'ipywe',
        _model_module_version : semver_range,
        _view_module_version : semver_range
    })
});

var ImgDataGraphView = widgets.DOMWidgetView.extend({

    //Overrides the default render method to allow for custom widget creation
    render: function() {
        //Wid is created to allow the model or DOM elements to be changed within enclosed functions.
        var wid = this;

        /*Creates the flexbox that will store the widget and the three flexitems that it will contain. This code also formats all of these items.
        widget_area is the overall flexbox that stores the entire widget.
        img_vbox is the flexitem that contains the image, canvas element, horizontal slider, horizontal slider label, and graph button.
        bin_vbox is the flexitem that contains the vertical slider and its label.
        graph_vbox is the flexitem that contains the graph created by the Python code.
        */
        var widget_area = $('<div class="flex-container">');
            
        widget_area.css("display", "-webkit-flex"); widget_area.css("display", "flex");
        widget_area.css("justifyContent", "flex-start"); widget_area.width(1000); widget_area.height(this.model.get("height") * 1.3);
            
        var img_vbox = $('<div class="flex-item-img img-box">');

        img_vbox.width(this.model.get("width") * 1.1); img_vbox.height(this.model.get("height") * 1.25); img_vbox.css("padding", "5px");

        var bin_vbox = $('<div class="flex-item-bin bin-box">');
        bin_vbox.width(150); bin_vbox.height(this.model.get("height") * 1.25); bin_vbox.css("padding", "5px");

        var graph_vbox = $('<div class="flex-item-graph graph-box">');

        graph_vbox.width(1000 - this.model.get("width") * 1.1 - 85); graph_vbox.height(this.model.get("height") * 1.25); graph_vbox.css("padding", "5px");

        //Adds the flexitems to the flexbox.
        widget_area.append(img_vbox);
        widget_area.append(bin_vbox);
        widget_area.append(graph_vbox);
        //Adds the flexbox to the display area.
        this.$el.append(widget_area);

        //Creates, formats, and adds the container for the image and canvas element.
        var img_container = $('<div class="img-container">');
        img_vbox.append(img_container);
        img_container.width(this.model.get("width")); img_container.height(this.model.get("height"));

        //Creates and formats the initial image
        var img = $('<img class="curr-img">');
        var image_src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value")
        img.attr("src", image_src);
        img_container.append(img);
        img.css("position", "absolute");
        img.width(this.model.get("width")); img.height(this.model.get("height"));

        //Creates the canvas element and stores the Rendering Context of the canvas in ctx for later use.
        var canvas = $('<canvas class="img-canvas">');
        canvas.prop({
            width: this.model.get("width"),
            height: this.model.get("height")
        });
        canvas.css("position", "absolute");
        img_container.append(canvas);
        var can = canvas[0];
        var ctx = can.getContext('2d');
        console.log(ctx);

        //Creates a read-only label input field with no border to dynamically display the value of the horizontal slider.
        var linewidth_label = $('<input class="lwidth-label" type="text" readonly style="border:0">');        

        //Calculates the maximum line width allowed
        var max_linewidth;
        if (this.model.get("width") < this.model.get("height")) {
            max_linewidth = this.model.get("width") / 4;
        }
        else {
            max_linewidth = this.model.get("height") / 4;
        }
        //Creates the horizontal slider using jQuery UI
        var width_slider = $('<div class="width-slider">');
        width_slider.slider({
            value: 1,
            min: 1,
            max: max_linewidth,
            /*When the handle is moved, this function updates the horizontal slider label and changes _linepix_width to whatever the slider's value is.
            */
            slide: function(event, ui) {
                linewidth_label.val("Line Width: " + ui.value + " px");
                wid.model.set("_linepix_width", ui.value);
                wid.touch();
            }
        });

        //Sets the initial value of the horizontal slider label and formats the label.
        linewidth_label.val("Line Width: " + width_slider.slider("value") + " px");
        linewidth_label.width("40%");
        //Formats the horizontal slider handle
        var width_slider_handle = width_slider.find(".ui-slider-handle");
        width_slider_handle.css("borderRadius", "50%");
        width_slider_handle.css("background", "#0099e6");
        //Formats the horizontal slider.
        width_slider.width(this.model.get("width"));
        width_slider.css({
            "marginLeft": "7px",
            "marginBottom": "5px",
            "marginTop": "20px"
        });
            
        //Adds the horizontal slider and its label to img_vbox
        img_vbox.append(width_slider);
        img_vbox.append(linewidth_label);

        //Creates, formats, and adds the graph button
        var graph_button = $('<button class="graph-button">');
        graph_button.button({
            label: "Graph",
            disabled: false
        });
        graph_button.css("marginLeft", "10px");
        img_vbox.append(graph_button);
        /*When this button is clicked, the _graph_click variable is updated (triggers the graph_data() Python function).
        */
        graph_button.click(function() {
            var graph_val = wid.model.get("_graph_click");
            if (graph_val < Number.MAX_SAFE_INTEGER) {
                graph_val++;
            }
            else {
                graph_val = 0;
            }
            wid.model.set("_graph_click", graph_val);
            wid.touch();
        });

        //Prevents the displayed image from deing dragged.
        img.on("dragstart", false);
            
        //Controls creating, changing, and displaying the currently drawn line
        canvas.on("mousedown", function(event) {
            //Resets the canvas, and stores the coordinates of the mousedown event in _offsetX1 and _offsetY1
            console.log("mousedown");
            ctx.clearRect(0, 0, wid.model.get("width"), wid.model.get("height"));
            var offx = event.offsetX;
            var offy = event.offsetY;
            wid.model.set("_offsetX1", offx);
            wid.model.set("_offsetY1", offy);
            wid.touch();
            canvas.on("mousemove", function(event) {
                /*Resets the canvas. If the ctrl key is not pressed, stores the coordinates of the mouse in _offsetX2 and _offsetY2. Otherwise, one of those variables will be set to the corresponding mouse coordinate, while the other one will be set so that it is the same as _offsetX1/_offsetY1.
               */
                console.log("mousemove");
                ctx.clearRect(0, 0, wid.model.get("width"), wid.model.get("height"));
                var currx = event.offsetX;
                var curry = event.offsetY;
                var slope = Math.abs((curry - offy) / (currx - offx))
                if (event.ctrlKey) {
                    if (slope <= 1) {
                        curry = offy
                    }
                    else {
                        currx = offx
                    }
                    }
                wid.model.set("_offsetX2", currx);
                wid.model.set("_offsetY2", curry);
                wid.touch();
                //Draws the line on the canvas
                ctx.beginPath();
                ctx.moveTo(offx, offy);
                ctx.lineTo(currx, curry);
                ctx.lineWidth = wid.model.get("_linepix_width") + 1;
                ctx.strokeStyle = "#ff0000";
                ctx.stroke();
            }).on("mouseup", function(event) {
                //Ends the mousemove event
                console.log("mouseup");
                canvas.off("mousemove");
            });
        });

        //Creats the vertical slider label
        var bin_slider_label = $('<input class="binslide-label" type="text" readonly style="border:0">');
        //Creates the vertical slider using jQuery UI
        var bin_slider = $('<div class="bin-slider">');
        bin_slider.slider({
            value: 1,
            min: 1,
            max: 100,
            orientation: "vertical",
        /*When the handle is moved, updates the vertical slider label, and sets the value of _num_bins.
            */
            slide: function(event, ui) {
                wid.model.set("_num_bins", ui.value);
                wid.touch();
                bin_slider_label.val("Number of Bins: " + ui.value);
            }
        });

        //Sets the initial value of the vertical slider label
        bin_slider_label.val("Histogram Bins: 1");
        //Formats the vertical slider
        bin_slider.height(this.model.get("height") * 0.9);
        bin_slider.css("marginTop", "5px");
        //Formats the vertical slider's handle
        var bin_slider_handle = bin_slider.find(".ui-slider-handle");
        bin_slider_handle.css("borderRadius", "50%");
        bin_slider_handle.css("background", "#0099e6");

        //Adds the vertical slider and its handle to bin_vbox
        bin_vbox.append(bin_slider_label);
        bin_vbox.append(bin_slider);

        //Creates, formats, and adds the graph. Note that the initial graph is simply a clear box.
        var graph_img = $('<img class="graph-img">');
        var graph_src = "data:image/" + this.model.get("_format") + ";base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
        graph_img.attr("src", graph_src);
        graph_vbox.append(graph_img);
        graph_img.css("position", "absolute");
        if (graph_vbox.width() <= graph_img.width()) {
            graph_img.width(graph_vbox.width() - 50);
        }

        //Triggers the functions below when the corresponding variable values change
        this.model.on("change:_b64value", this.on_img_change, this);
        this.model.on("change:_graphb64", this.on_graph_change, this);
        this.model.on("change:_linepix_width", this.on_linewidth_change, this);
    },

    /*When _b64value changes, this function creates a new source string for the image and replaces the old one with the new one.
    */
    on_img_change: function() {
        var src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value");
        this.$el.find(".curr-img").attr("src", src);
    },

    /*When _graphb64 changes, this function creates a new source string for the graph and replaces the old one with the new one.
    */
    on_graph_change: function() {
        var src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_graphb64");
        this.$el.find(".graph-img").attr("src", src);
    },

    /*When _linepix_width changes, this function creates a new line with the same endpoints as the currently displayed line, but with a width equal to the new value. 
    */
    on_linewidth_change: function() {
        var canvas = this.$el.find(".img-canvas")[0];
        var ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, this.model.get("width"), this.model.get("height"));
        ctx.beginPath();
        ctx.moveTo(this.model.get("_offsetX1"), this.model.get("_offsetY1"));
        ctx.lineTo(this.model.get("_offsetX2"), this.model.get("_offsetY2"));
        ctx.lineWidth = this.model.get("_linepix_width") + 1;
        ctx.strokeStyle = "#ff0000";
        ctx.stroke();
    }

});

module.exports = {
    ImgDataGraphView : ImgDataGraphView,
    ImgDataGraphModel : ImgDataGraphModel
};

