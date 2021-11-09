// Entry point for the unpkg bundle containing custom model definitions.
//
// It differs from the notebook bundle in that it does not need to define a
// dynamic baseURL for the static assets and may load some css that would
// already be loaded by the notebook otherwise.

// add ligher styles here
module.exports = require('./loadwidgets');
// module.exports = require('./example.js');
module.exports['version'] = require('../package.json').version;
