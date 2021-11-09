var widgets = require('jupyter-js-widgets');
var _ = require('underscore');
var semver_range = "^" + require("../package.json").version;

var ImgSliderModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(_.result(this, 'widgets.DOMWidgetModel.prototype.defaults'), {
        _model_name : 'ImgSliderModel',
        _view_name : 'ImgSliderView',
        _model_module : 'ipywe',
        _view_module : 'ipywe',
        _model_module_version : semver_range,
        _view_module_version : semver_range
    })
});


var ImgSliderView = widgets.DOMWidgetView.extend({
	
    //Overrides the default render method to allow for custom widget creation
    
    render: function() {

        //Sets all the values needed for creating the sliders. wid is created to allow model values to be obtained in functions within this render function.
        var wid = this;
        var img_index_max = this.model.get("_N_images") - 1;
        var vrange_min = this.model.get("_img_min");
        var vrange_max = this.model.get("_img_max");
        var vrange_step = (vrange_max - vrange_min)/100;
        var vrange = [vrange_min, vrange_max];

        /*Creates the flexbox that will store the widget and the two flexitems that it will contain. Also formats all of them.
          img_vbox stores the image and the horizontal (Image Selector) slider.
          data_vbox stores the html text element (displays the XY coordinates of the mouse and that position's value) and the vertical (Z range) slider.*/

        var widget_area = $('<div class="flex-container">');
        
        widget_area.css("display", "-webkit-flex"); widget_area.css("display", "flex");
        widget_area.css("justifyContent", "flex-start"); widget_area.width(1000); widget_area.height(this.model.get("height") * 1.3);
        
        var img_vbox = $('<div class="flex-item-img img-box">');

        img_vbox.width(this.model.get("width") * 1.1); img_vbox.height(this.model.get("height") * 1.25); img_vbox.css("padding", "5px");

        var data_vbox = $('<div class="flex-item-data data-box">');

        data_vbox.width(1000 - this.model.get("width") * 1.1 - 25); data_vbox.height(this.model.get("height") * 1.25); data_vbox.css("padding", "5px");

        //Adds the img_vbox and data_vbox to the overall flexbox.

        widget_area.append(img_vbox);
        widget_area.append(data_vbox);

        //Adds the widget to the display area.
        this.$el.append(widget_area);

        //Add a container for the image and the selection box
        var img_container = $('<div class="img-container">');
        img_vbox.append(img_container);
        img_container.css({
            position: "relative",
            width: this.model.get("width"),
            height: this.model.get("height")
            //padding: "10px"
        });

        //Creates the image stored in the initial value of _b64value and adds it to img_vbox.
        var img = $('<img class="curr-img">');
        var image_src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value")
        img.attr("src", image_src);
        
        img.width(this.model.get("width")); img.height(this.model.get("height"));
        img_container.append(img);

        //Creates a read-only input field with no border to dynamically display the value of the horizontal slider.
        var hslide_label = $('<input class="hslabel" type="text" readonly style="border:0">'); 
        //Creates the horizontal slider using JQuery UI
        var hslide_html = $('<div class="hslider">');
        hslide_html.slider({
            value: 0,
            min: 0,
            max: img_index_max,
            /*When the handle slides, this function is called to update hslide_label 
              and change _img_index on the backend (triggers the update_image_index function on the backend)*/
            slide: function(event, ui) {
                hslide_label.val( ui.value );
                console.log("Executed!");
                wid.model.set("_img_index", ui.value);
                wid.touch();
            }
        });
        
        //Sets the label's initial value to the initial value of the slider and adds a left margin to the label
        hslide_label.val(hslide_html.slider("value"));
        hslide_label.width("15%");
        //Makes the slider's handle a blue circle and adds a 10 pixel margin to the slider
        var hslide_handle = hslide_html.find(".ui-slider-handle");
        hslide_handle.css("borderRadius", "50%");
        hslide_handle.css("background", "#0099e6");
        hslide_html.width(this.model.get("width"));
        hslide_html.css("marginLeft", "7px");
        hslide_html.css("marginBottom", "5px");
        hslide_html.css("marginTop", "20px");
        //Adds hslide_html (the slider) and hslide_label (the label) to img_vbox
        img_vbox.append(hslide_html);
        img_vbox.append(hslide_label);

        //Creates and adds a button after hslide_label for zooming into a single image
        var zoom_button = $('<button class="zoom-button">');
        zoom_button.button({
            label: "Zoom",
            disabled: false
        });
        zoom_button.css("margin", "10px");
        img_vbox.append(zoom_button);
        /*When zoom_button is clicked, the ROI is passed back to the python side.
          This triggeres the zoom_image python function. The selection box is also removed.
        */
        zoom_button.click(function() {
	    ; //
	    var ROI = select.data("ROI");
	    console.log(ROI);
	    if (typeof ROI == 'undefined') return;
	    wid.model.set("_ROI", ROI);
	    wid.touch();
            select.remove();
            console.log("Zoomed");
        });

        //Creates and adds a button after zoomall_button for reseting all displayed images.
        var reset_button = $('<button class="reset-button">')
        reset_button.button({
            label: "Reset",
            disabled: false
        });
        reset_button.css("margin", "10px");
        img_vbox.append(reset_button);
        /*When reset_button is clicked, ROI is set to negative numbers.
          This triggers the zoom_image python function. The selection box is also removed.
        */
        reset_button.click(function() {
	    wid.model.set("_ROI", [-1,-1,-1,-1]);
            wid.touch();
            select.remove();
            console.log("Image reset");
        });

        //Creates the selection box's div.
        var select = $('<div class="selection-box">');

        //Prevents the displayed image from being dragged (done to prevent issues with the following code.
        img.on("dragstart", false);

        //Controls creating, changing, and displaying the selection box.
        img_container.on("mousedown", function(event) {
            console.log("Click 1");
            var click_x = event.offsetX;
            var click_y = event.offsetY;
            
            //Initializes the selection box and adds it to img_container
            select.css({
                "top": click_y,
                "left": click_x,
                "width": 0,
                "height": 0,
                "position": "absolute",
                "pointerEvents": "none"
            });

            
            select.appendTo(img_container);

            img_container.on("mousemove", function(event) {
                console.log("Mouse moving");
                var move_x = event.offsetX;
                var move_y = event.offsetY;
                var width = Math.abs(move_x - click_x);
                var height = Math.abs(move_y - click_y);
                var new_x, new_y;

                /*The logic that allows the creation of a selection box where the final
                  mouse position is up and left from the initial position.
                */
                new_x = (move_x < click_x) ? (click_x - width) : click_x;
                new_y = (move_y < click_y) ? (click_y - height) : click_y;

                /*As the mouse moves, this statement dynamically resizes the selection
                  box.
                */
                select.css({
                    "width": width,
                    "height": height,
                    "top": new_y,
                    "left": new_x,
                    "background": "transparent",
                    "border": "2px solid red"
                });

                //Sets the variables used to splice the image's data on the backend
		select.data("ROI", 
			    [parseInt(select.css("left"), 10), //_offXtop
			     parseInt(select.css("top"), 10),  //_offYtop
			     parseInt(select.css("left"), 10) + select.width(), // _offXbottom
			     parseInt(select.css("top"), 10) + select.height()  // _offYbottom
			     ]);
            }).on("mouseup", function(event) {
                //Turns the mousemove event off to stop resizing the selection box.
                console.log("Click 2");
                img_container.off("mousemove");
            });
        });
	    // wid.model.set("_offXbottom"
        console.log(img_vbox);
        console.log("done with img box");

        //Creates the fields (divs and spans) for the current mouse position and that position's value and adds them to data_vbox.
        var text_content = $('<div class="widget-html-content">');
        var xy = $("<div>"); xy.text("X,Y: ");
        var x_coord = $('<span class="img-offsetx">');
        var y_coord = $('<span class="img-offsety">');
        xy.append(x_coord); xy.append(", "); xy.append(y_coord);
        var value = $("<div>"); value.text("Value: ");
        var val = $('<span class="img-value">');
        value.append(val);
        var roi = $("<div>"); roi.text("ROI: ");
        var corners = $('<span class="roi">');
        roi.append(corners);
        corners.css("whiteSpace", "pre");
        text_content.append(xy); text_content.append(value); text_content.append(roi);
        data_vbox.append(text_content);
        console.log(data_vbox);
        
        //Creates the label for the vertical slider with a static value of "Z range" (done in the same way as the other label)
        var vslide_label = $('<div class="vslabel" type="text" readonly style="border:0">');
        vslide_label.text("Z range: ");
        vslide_label.css("marginTop", "10px");
        vslide_label.css("marginBottom", "10px");
        var vslide_labeldata = $('<span class="vslabel_data">');
        var vlabel_content = "Max Range: " + vrange + "\n              Current Range: " + vrange;
        vslide_labeldata.text(vlabel_content);
        vslide_labeldata.css("whiteSpace", "pre");
        vslide_label.append(vslide_labeldata);
        //Creates the vertical slider using JQuery UI
        var vslide_html = $('<div class="vslider">');
        vslide_html.slider({
            range: true,
            orientation: "vertical",
            min: vrange_min,
            max: vrange_max,
            values: vrange,
            step: vrange_step,
            /*When either handle slides, this function updates this slider's label to reflect the new contrast range. It also sets _img_min and/or _img_max on the backend to the handles' values.
              This triggers the update_image_div_data function on the backend.*/
            slide: function(event, ui) {
                vlabel_content = "Max Range: " + vrange + "\n              Current Range: " + ui.values;
                wid.$el.find(".vslabel_data").text(vlabel_content);
                wid.model.set("_img_min", ui.values[0]);
                wid.model.set("_img_max", ui.values[1]);
                wid.touch();
            }
        });

        
        //Explicitly sets the slider's background color to white. Also, changes the handles to blue circles
        var vslide_bar = vslide_html.find(".ui-widget-header");
        vslide_bar.css("background", "#ffffff");
        vslide_bar.siblings().css("borderRadius", "50%");
        vslide_bar.siblings().css("background", "#0099e6");
        //Adds vslide_label and vslide_html to data_vbox. At this point, the widget can be successfully displayed.
        if (this.model.get("height") >= 150) {
            vslide_html.height(this.model.get("height") - 100);
        }
        else {
            vslide_html.height(50);
        }
        data_vbox.append(vslide_label);
        data_vbox.append(vslide_html);
        console.log(data_vbox);
        console.log("done with data box");

        
        /*This function sets _offsetX and _offsetY on the backend to the event-specific offset values whenever
          the mouse moves over the image. It then calculates the data-based XY coordinates and displays them
          in the x_coord and y_coord span fields.*/
        img.mousemove(function(event){
            wid.model.set("_offsetX", event.offsetX);
            wid.model.set("_offsetY", event.offsetY);
            wid.touch();

            //console.log(wid.model.get("_extrarows"), wid.model.get("_extracols"));
            var yrows_top, yrows_bottom, xcols_left, xcols_right, x_coordinate, y_coordinate;
            x_coordinate = Math.floor(event.offsetX*1./(wid.model.get("width"))*(wid.model.get("_ncols_currimg")));
            y_coordinate = Math.floor(event.offsetY*1./(wid.model.get("height"))*(wid.model.get("_nrows_currimg")));

            //All of this logic is used to get the correct coordinates for images containing buffer rows/columns.
            if (wid.model.get("_extrarows") == 0 && wid.model.get("_extracols") == 0) {
                //console.log("No extra rows/cols");
                yrows_top = 0;
                yrows_bottom = Number.MAX_SAFE_INTEGER;
                xcols_left = 0;
                xcols_right = Number.MAX_SAFE_INTEGER;
            }
            else if (wid.model.get("_extrarows") != 0 && wid.model.get("_extracols") == 0) {
                //console.log("Extra Rows");
                if (wid.model.get("_extrarows") % 2 == 0) {
                    yrows_top = parseInt(wid.model.get("_extrarows") / 2);
                    yrows_bottom = parseInt(wid.model.get("_extrarows") / 2);
                }
                else {
                    yrows_top = parseInt(wid.model.get("_extrarows") / 2 + 1);
                    yrows_bottom = parseInt(wid.model.get("_extrarows") / 2);
                }
                xcols_left = 0;
                xcols_right = Number.MAX_SAFE_INTEGER;
            }
            else if (wid.model.get("_extrarows") == 0 && wid.model.get("_extracols") != 0) {
                //console.log("Extra Cols");
                if (wid.model.get("_extracols") % 2 == 0) {
                    xcols_left = parseInt(wid.model.get("_extracols") / 2);
                    xcols_right = parseInt(wid.model.get("_extracols") / 2);
                }
                else {
                    xcols_left = parseInt(wid.model.get("_extracols") / 2 + 1);
                    xcols_right = parseInt(wid.model.get("_extracols") / 2);
                }
                yrows_top = 0;
                yrows_bottom = Number.MAX_SAFE_INTEGER;
            }
            else {
                //console.log("Extra Rows/Cols");
                if (wid.model.get("_extrarows") % 2 == 0) {
                    yrows_top = parseInt(wid.model.get("_extrarows") / 2);
                    yrows_bottom = parseInt(wid.model.get("_extrarows") / 2);
                }
                else {
                    yrows_top = parseInt(wid.model.get("_extrarows") / 2 + 1);
                    yrows_bottom = parseInt(wid.model.get("_extrarows") / 2);
                }
                if (wid.model.get("_extracols") % 2 == 0) {
                    xcols_left = parseInt(wid.model.get("_extracols") / 2);
                    xcols_right = parseInt(wid.model.get("_extracols") / 2);
                }
                else {
                    xcols_left = parseInt(wid.model.get("_extracols") / 2 + 1);
                    xcols_right = parseInt(wid.model.get("_extracols") / 2);
                }
            }

            /*If the mouse is in a buffer area, the text for the x_coord and y_coord HTML fields are set to empty strings.
              Otherwise, these text elements are set to be a string containing the mouse position relative to the 
              original, un-zoomed image.
            */
            if (y_coordinate < yrows_top || (y_coordinate > wid.model.get("_nrows_currimg") - yrows_bottom && yrows_bottom != Number.MAX_SAFE_INTEGER) || x_coordinate < xcols_left || (x_coordinate > wid.model.get("_ncols_currimg") - xcols_right && xcols_right != Number.MAX_SAFE_INTEGER)) {
                x_coord.text("");
                y_coord.text("");
            }
            else {
                x_coord.text((x_coordinate - xcols_left) + wid.model.get("_xcoord_absolute"));
                y_coord.text((y_coordinate - yrows_top) + wid.model.get("_ycoord_absolute"));
            }
        });

        this.calc_roi();

        //Triggers on_pixval_change and on_img_change when the backend values of _pix_val and _b64value change.
        this.model.on("change:_pix_val", this.on_pixval_change, this);
        this.model.on("change:_b64value", this.on_img_change, this);
        this.model.on("change:_b64value", this.calc_roi, this);
        this.model.on("change:_vslide_reset", this.reset_vslide, this);
    },

    /*If the text of the coordinate fields (x_coord and y_coord) contain empty strings, the value field will 
      also be set to an empty string. Otherwise, if there is no custom error message, this field will be
      set to the image's value at the mouse's position. If there is a custom error message, it will be
      displayed in the value field.
    */
    on_pixval_change: function() {
        //console.log("Executing on_pixval_change");
        if (this.$el.find(".img-offsetx").text() == "" && this.$el.find(".img-offsety").text() == "") {
            this.$el.find(".img-value").text("");
        }
        else {
            if (this.model.get("_err") == "") {
                this.$el.find(".img-value").text(this.model.get("_pix_val"));
            }
            else {
                this.$el.find(".img-value").text(this.model.get("_err"));
            }
        }
    },

    /*When _b64value changes on the backend, this function creates a new source string for the image (based
      on the new value of _b64value). This new source then replaces the old source of the image.*/
    on_img_change: function() {
        //console.log("Executing on_img_change");
        var src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value");
        this.$el.find(".curr-img").attr("src", src);
    },

    /*When _b64value changes on the backend, this function will calculate and display the coordinates of the left, right, top, and bottom borders of the currently displayed image. Note that these coordinates are based on the original, un-zoomed image.
     */
    calc_roi: function() {
        /*var top = this.model.get("_ycoord_absolute");
        var left = this.model.get("_xcoord_absolute");
        var right = this.model.get("_xcoord_absolute") + this.model.get("_ncols_currimg") - this.model.get("_extracols");
        var bottom = this.model.get("_ycoord_absolute") + this.model.get("_nrows_currimg") - this.model.get("_extrarows");*/
        var corns = "Top = " + this.model.get("_ycoord_absolute") + "   Bottom = " + this.model.get("_ycoord_max_roi") + "\n         Left = " + this.model.get("_xcoord_absolute") + "   Right = " + this.model.get("_xcoord_max_roi");
        console.log(corns);
        this.$el.find(".roi").text(corns);
    },

    /*When the reset button is pressed, this function will reset the vertical slider's handle positions and values to what they were originally. It also resets the value of the vertical slider's label to its default.
     */
    reset_vslide: function() {
        $(".vslider").slider("values", 0, this.model.get("_img_min"));
        $(".vslider").slider("values", 1, this.model.get("_img_max"));
        var vrange_str = this.model.get("_img_min") + "," + this.model.get("_img_max");
        $(".vslabel_data").text("Max Range: " + vrange_str + "\n              Current Range: " + vrange_str);
    }
    
});

module.exports = {
    ImgSliderView : ImgSliderView,
    ImgSliderModel : ImgSliderModel
};
