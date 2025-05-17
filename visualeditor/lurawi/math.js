/**
 * @license
 * Visual Blocks Language
 *
 * Copyright 2012 Google Inc.
 * https://developers.google.com/blockly/
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @fileoverview Generating LurawiKit for math blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

Blockly.LurawiKit['math_number'] = function(block) {
  // Numeric value.
  var code = parseFloat(block.getFieldValue('NUM'));
  var order;
  if (code == Infinity) {
    code = 'float("inf")';
    order = Blockly.LurawiKit.ORDER_FUNCTION_CALL;
  } else if (code == -Infinity) {
    code = '-float("inf")';
    order = Blockly.LurawiKit.ORDER_UNARY_SIGN;
  } else {
    order = code < 0 ? Blockly.LurawiKit.ORDER_UNARY_SIGN :
            Blockly.LurawiKit.ORDER_ATOMIC;
  }
  return [code, order];
};

Blockly.LurawiKit['math_arithmetic'] = function(block) {
  // Basic arithmetic operators, and power.
  var OPERATORS = {
    'ADD': [' + ', Blockly.LurawiKit.ORDER_ADDITIVE],
    'MINUS': [' - ', Blockly.LurawiKit.ORDER_ADDITIVE],
    'MULTIPLY': [' * ', Blockly.LurawiKit.ORDER_MULTIPLICATIVE],
    'DIVIDE': [' / ', Blockly.LurawiKit.ORDER_MULTIPLICATIVE],
    'POWER': [' ** ', Blockly.LurawiKit.ORDER_EXPONENTIATION]
  };
  var tuple = OPERATORS[block.getFieldValue('OP')];
  var operator = tuple[0];
  var order = tuple[1];
  var argument0 = Blockly.LurawiKit.valueToCode(block, 'A', order) || '0';
  var argument1 = Blockly.LurawiKit.valueToCode(block, 'B', order) || '0';
  // the parent block assume to be a variable and it should reprocess this
  var code = 'calculate:' + argument0 + operator + argument1;
  return [code, order];
};

Blockly.LurawiKit['math_change'] = function(block) {
  // Add to a variable in place.
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'DELTA',
        Blockly.LurawiKit.ORDER_ADDITIVE) || '0';
    var varName = Blockly.LurawiKit.nameDB_.getName(block.getFieldValue('VAR'),
      Blockly.Names.NameType.VARIABLE).toUpperCase();

    var code = '["calculate", ["'+ varName + '", "' + varName + (argument0 >= 0 ? ' + ' : ' - ') + Math.abs(argument0) + '"]]';
    return code + (block.getNextBlock() ? ',\n' : '\n');
};
