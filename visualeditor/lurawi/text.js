/**
 * @fileoverview Generating LurawiKit for text blocks.
 * @author q.neutron@gmail.com (Quynh Neutron)
 */
'use strict';

Blockly.LurawiKit['text'] = function(block) {
  // Text value.
  var code = Blockly.LurawiKit.quote_(block.getFieldValue('TEXT') || '') ;
  return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};

Blockly.LurawiKit['text_join'] = function(block) {
  // Create a string made up of any number of elements of any type.
  //Should we allow joining by '-' or ',' or any other characters?
  switch (block.itemCount_) {
    case 0:
      return ['""', Blockly.LurawiKit.ORDER_ATOMIC];
      break;
    default:
      var code = '"';
      var variable_list = [];
      for (var i = 0; i < block.itemCount_; i++) {
        var element = Blockly.LurawiKit.valueToCode(block, 'ADD' + i,
                Blockly.LurawiKit.ORDER_NONE) || '\'\'';
        if (element === element.toUpperCase()) { // element is a variable
            code = code + '{}';
            variable_list.push(element);
        }
        else {
            code = code + element.slice(1,-1);
        }
      }
      if (variable_list.length > 0) {
          code = '[' + code +'", [' + variable_list.join(',') + ']]';
      }
      else {
          code = code + '"';
      }
      return [code, Blockly.LurawiKit.ORDER_FUNCTION_CALL];
  }
};
