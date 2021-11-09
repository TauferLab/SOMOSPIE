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
var VtkJsModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(_.result(this, 'widgets.DOMWidgetModel.prototype.defaults'), {
	_model_name : 'VtkJsModel',
	_view_name : 'VtkJsView',
	_model_module : 'ipywe',
	_view_module : 'ipywe',
	_model_module_version : '0.1.0',
	_view_module_version : '0.1.0',
	value : 'Hello World'
    })
});


// Custom View. Renders the widget model.
var VtkJsView = widgets.DOMWidgetView.extend({
    render: function() {
        var widget_area = $('<div>');
        this.$el.append(widget_area);
        var container = widget_area.get(0);
	var url = this.model.get("url");

        $.getScript('https://unpkg.com/vtk.js').done(function(){

		var vtkColorTransferFunction = vtk.Rendering.Core.vtkColorTransferFunction;
		var vtkFullScreenRenderWindow = vtk.Rendering.Misc.vtkFullScreenRenderWindow;
		var  vtkHttpDataSetReader  = vtk.IO.Core.vtkHttpDataSetReader;
		var  vtkXMLImageDataReader  = vtk.IO.XML.vtkXMLImageDataReader;
		var vtkPiecewiseFunction = vtk.Common.DataModel.vtkPiecewiseFunction;
		var  vtkVolume = vtk.Rendering.Core.vtkVolume;
		var  vtkVolumeMapper = vtk.Rendering.Core.vtkVolumeMapper;
		//
		// Standard rendering code setup
		var renderWindow = vtk.Rendering.Core.vtkRenderWindow.newInstance();
		var renderer = vtk.Rendering.Core.vtkRenderer.newInstance({ background: [0.2, 0.3, 0.4] });
		renderWindow.addRenderer(renderer);
    
		// different data needs different reader. 
		// const reader = vtkHttpDataSetReader.newInstance({ fetchGzip: true });
		// VTI reader
		const reader = vtkXMLImageDataReader.newInstance();
		const actor = vtkVolume.newInstance();
		const mapper = vtkVolumeMapper.newInstance();
		mapper.setSampleDistance(1.1);
		actor.setMapper(mapper);
		// create color and opacity transfer functions
		const ctfun = vtkColorTransferFunction.newInstance();
		ctfun.addRGBPoint(0, 85 / 255.0, 0, 0);
		ctfun.addRGBPoint(95, 1.0, 1.0, 1.0);
		ctfun.addRGBPoint(225, 0.66, 0.66, 0.5);
		ctfun.addRGBPoint(255, 0.3, 1.0, 0.5);
		const ofun = vtkPiecewiseFunction.newInstance();
		ofun.addPoint(0.0, 0.0);
		ofun.addPoint(255.0, 1.0);

		// reader.setUrl(`/~lj7/LIDC2.vti`).then(() => {
		reader.setUrl(url).then(() => {
			reader.loadData().then(() => {
				//
				const source = reader.getOutputData(0);
				// mapper.setInputConnection(reader.getOutputPort());
				console.log(source);
				mapper.setInputData(source);
				const dataArray = source.getPointData().getScalars() || source.getPointData().getArrays()[0];
				const dataRange = dataArray.getRange();
				console.log("dataRange=", dataRange);
				actor.getProperty().setRGBTransferFunction(0, ctfun);
				actor.getProperty().setScalarOpacity(0, ofun);
				actor.getProperty().setScalarOpacityUnitDistance(0, 3.0);
				actor.getProperty().setInterpolationTypeToLinear();
				actor.getProperty().setUseGradientOpacity(0, true);
				actor.getProperty().setGradientOpacityMinimumValue(0, 0);
				actor.getProperty().setGradientOpacityMinimumOpacity(0, 0.0);
				actor.getProperty().setGradientOpacityMaximumValue(0, (dataRange[1] - dataRange[0]) * 0.05);
				actor.getProperty().setGradientOpacityMaximumOpacity(0, 1.0);
				actor.getProperty().setShade(true);
				actor.getProperty().setAmbient(0.2);
				actor.getProperty().setDiffuse(0.7);
				actor.getProperty().setSpecular(0.3);
				actor.getProperty().setSpecularPower(8.0);

				renderer.addVolume(actor);
				renderer.resetCamera();

				var openglRenderWindow = vtk.Rendering.OpenGL.vtkRenderWindow.newInstance();
				renderWindow.addView(openglRenderWindow);
				openglRenderWindow.setContainer(container);

				renderer.getActiveCamera().zoom(1.5);
				renderer.getActiveCamera().elevation(70);

				var interactor =     vtk.Rendering.Core.vtkRenderWindowInteractor.newInstance();
				interactor.setView(openglRenderWindow);
				interactor.initialize();
				interactor.setDesiredUpdateRate(15.0);
				interactor.bindEvents(container);

				renderWindow.render();
			    });
		    });
		// end of setUrl

	    }); // end of getScript
	
    }
});


module.exports = {
    VtkJsModel : VtkJsModel,
    VtkJsView : VtkJsView
};
