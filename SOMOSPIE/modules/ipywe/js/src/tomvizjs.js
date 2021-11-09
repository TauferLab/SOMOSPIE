// var devel=1;
var devel=0;
var widgets = require('jupyter-js-widgets');
var _ = require('underscore');

// Custom Model. Custom widgets models must at least provide default values
// for model attributes, including
//
//  - `_view_name`
//  - `_view_module`
//  - `_view_module_version`
//
//  - `_model_name`
//  - `_model_module`
//  - `_model_module_version`
//
//  when different from the base class.

// When serialiazing the entire widget state for embedding, only values that
// differ from the defaults will be specified.
var TomvizJsModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(_.result(this, 'widgets.DOMWidgetModel.prototype.defaults'), {
	_model_name : 'TomvizJsModel',
	_view_name : 'TomvizJsView',
	_model_module : 'ipywe',
	_view_module : 'ipywe',
	_model_module_version : '0.1.0',
	_view_module_version : '0.1.0',
	value : 'Hello World'
    })
});


// Custom View. Renders the widget model.
var TomvizJsView = widgets.DOMWidgetView.extend({
    render: function() {
        var s= '<div class="tomviz-data-viewer" data-url="' + this.model.get("url") + '" '
            + 'data-viewport="100%x500" '
            + 'data-no-ui data-initialization="zoom=1.5" data-step="azimuth=10" data-animation="azimuth=100" /> ';
        var js = '<script type="text/javascript" src="https://unpkg.com/tomvizweb"></script>';
        var widget_area = $(s);
        this.$el.append(widget_area);
        $.getScript('https://unpkg.com/tomvizweb');
    }
});


module.exports = {
    TomvizJsModel : TomvizJsModel,
    TomvizJsView : TomvizJsView
};
