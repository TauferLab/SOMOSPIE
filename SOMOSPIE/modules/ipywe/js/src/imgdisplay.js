var widgets = require('jupyter-js-widgets');
var _ = require('underscore');
var semver_range = "^" + require("../package.json").version;

var ImgDisplayModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(_.result(this, 'widgets.DOMWidgetModel.prototype.defaults'), {
        _model_name : 'ImgDisplayModel',
        _view_name : 'ImgDisplayView',
        _model_module : 'ipywe',
        _view_module : 'ipywe',
        _model_module_version : semver_range,
        _view_module_version : semver_range
    })
});


var ImgDisplayView = widgets.DOMWidgetView.extend({
    
    render: function() {
        var wid = this;

        var widget_area = $('<div class="flex-container">');

        widget_area.css("display", "-webkit-flex"); widget_area.css("display", "flex");
        widget_area.css("jusitfyContent", "flex-start"); widget_area.width(1000);
        widget_area.height(this.model.get("height") * 1.3);

        var img_vbox = $('<div class="flex-item-img img-box">');

        img_vbox.width(this.model.get("width") * 1.1); img_vbox.height(this.model.get("height") * 1.25); img_vbox.css("padding", "5px");

        var roi_vbox = $('<div class="flex-item-roi roi-box">');

        roi_vbox.width(1000 - (this.model.get("width") * 1.1) - 25); roi_vbox.height(this.model.get("height") * 1.25); roi_vbox.css("padding", "5px");

        widget_area.append(img_vbox);
        widget_area.append(roi_vbox);

        this.$el.append(widget_area);

        var img_container = $('<div class="img-container">');
        img_vbox.append(img_container);
        img_container.css({
            position: "relative",
            width: this.model.get("width"),
            height: this.model.get("height")
        });
        
        var img = $('<img class="curr-img">');
        var image_src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value")
        img.attr("src", image_src);
        img.width(this.model.get("width")); img.height(this.model.get("height"));
        img_container.append(img);
        //this.$el.append(img);

        var zoom_button = $('<button class="zoom-button">');
        zoom_button.button({
            label: "Zoom",
            disabled: false
        });
        zoom_button.css("margin", "10px");
        zoom_button.css("marginLeft", "0px");
        img_vbox.append(zoom_button);
        zoom_button.click(function() {
            var zoom_val = wid.model.get("_zoom_click");
            if (zoom_val < Number.MAX_SAFE_INTEGER) {
                zoom_val++;
            }
            else {
                zoom_val = 0;
            }
            wid.model.set("_zoom_click", zoom_val);
            wid.touch();
            select.remove();
            console.log("Select removed");
        });

        var reset_button = $('<button class="reset-button">')
        reset_button.button({
            label: "Reset",
            disabled: false
        });
        reset_button.css("margin", "10px");
        img_vbox.append(reset_button);
        reset_button.click(function() {
            var reset_val = wid.model.get("_reset_click");
            if (reset_val < Number.MAX_SAFE_INTEGER) {
                reset_val++;
            }
            else {
                reset_val = 0;
            }
            wid.model.set("_reset_click", reset_val);
            wid.touch();
            select.remove();
            console.log("Image reset");
        });

        var select = $('<div class="selection-box">');
        select.appendTo(img_container);

        if (this.model.get("_offXtop") != 0 && this.model.get("_offXbottom") != 0 && this.model.get("_offYtop") != 0 && this.model.get("_offYbottom") != 0) {
            //console.log(this.model.get("_offXtop"));
            //console.log(this.model.get("_offXbottom"));
            //console.log(this.model.get("_offYtop"));
            //console.log(this.model.get("_offYbottom"));
            console.log("entered")
            var sel_width = this.model.get("_offXbottom") - this.model.get("_offXtop");
            var sel_height = this.model.get("_offYbottom") - this.model.get("_offYtop");
            select.css({
                "top": this.model.get("_offYtop"),
                "left": this.model.get("_offXtop"),
                "width": sel_width,
                "height": sel_height,
                "position": "absolute",
                "pointerEvents": "none",
                "background": "transparent",
                "border": "2px solid red"
            });
        }

        img.on("dragstart", false);

        img.on("mousedown", function(event) {
            console.log("Click 1");
            var click_x = event.offsetX;
            var click_y = event.offsetY;
            
            select.css({
                "top": click_y,
                "left": click_x,
                "width": 0,
                "height": 0,
                "position": "absolute",
                "pointerEvents": "none"
            });

            select.appendTo(img_container);

            img.on("mousemove", function(event) {
                console.log("Mouse moving");
                var move_x = event.offsetX;
                var move_y = event.offsetY;
                var width = Math.abs(move_x - click_x);
                var height = Math.abs(move_y - click_y);
                var new_x, new_y;

                new_x = (move_x < click_x) ? (click_x - width) : click_x;
                new_y = (move_y < click_y) ? (click_y - height) : click_y;

                select.css({
                    "width": width,
                    "height": height,
                    "top": new_y,
                    "left": new_x,
                    "background": "transparent",
                    "border": "2px solid red"
                });

                console.log(select);

                wid.model.set("_offXtop", parseInt(select.css("left"), 10));
                wid.model.set("_offYtop", parseInt(select.css("top"), 10));
                wid.model.set("_offXbottom", parseInt(select.css("left"), 10) + select.width());
                wid.model.set("_offYbottom", parseInt(select.css("top"), 10) + select.height());
                wid.touch();

            }).on("mouseup", function(event) {
                console.log("Click 2");
                img.off("mousemove");
            });
        });

        var roi = $("<div>"); roi.text("ROI: ");
        var corners = $('<span class="roi">');
        roi.append(corners);
        corners.css("whiteSpace", "pre");
        roi_vbox.append(roi);

        this.calc_roi();
        
        this.model.on("change:_b64value", this.calc_roi, this);
        this.model.on("change:_b64value", this.on_img_change, this);
    },

    on_img_change: function() {
        var src = "data:image/" + this.model.get("_format") + ";base64," + this.model.get("_b64value");
        this.$el.find(".curr-img").attr("src", src);
    },

    calc_roi: function() {
        /*var top = this.model.get("_ycoord_absolute");
        var left = this.model.get("_xcoord_absolute");
        var right = this.model.get("_xcoord_absolute") + this.model.get("_ncols_currimg") - this.model.get("_extracols");
        var bottom = this.model.get("_ycoord_absolute") + this.model.get("_nrows_currimg") - this.model.get("_extrarows");*/
        var corns = "Top = " + this.model.get("_ycoord_absolute") + "   Bottom = " + this.model.get("_ycoord_max_roi") + "\n         Left = " + this.model.get("_xcoord_absolute") + "   Right = " + this.model.get("_xcoord_max_roi");
        console.log(corns);
        this.$el.find(".roi").text(corns);
    }

});

module.exports = {
    ImgDisplayView : ImgDisplayView,
    ImgDisplayModel : ImgDisplayModel
};
