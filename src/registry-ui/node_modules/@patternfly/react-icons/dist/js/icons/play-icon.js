"use strict"
exports.__esModule = true;
exports.PlayIconConfig = {
  name: 'PlayIcon',
  icon: {"xOffset":0,"yOffset":0,"width":448,"height":512,"svgPathData":"M424.4 214.7L72.4 6.6C43.8-10.3 0 6.1 0 47.9V464c0 37.5 40.7 60.1 72.4 41.3l352-208c31.4-18.5 31.5-64.1 0-82.6z"},
  rhUiIcon: {"xOffset":0,"yOffset":0,"width":32,"height":32,"svgPathData":"m30.447 15.105-28-14A1.001 1.001 0 0 0 1 2v28a1.003 1.003 0 0 0 1 1c.153 0 .306-.035.447-.105l28-14a1 1 0 0 0 0-1.79ZM3 28.382V3.618L27.764 16 3 28.382Z"},
};
exports.PlayIcon = require('../createIcon').createIconBase(exports.PlayIconConfig);
exports["default"] = exports.PlayIcon;