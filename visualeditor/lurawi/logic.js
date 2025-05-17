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
 * @fileoverview Generating LurawiKit for logic blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

function concatenate_actions(content) {
  let obj = JSON.parse(content);
  let subblocks = Object.values(obj)[0]
  let text = `"${Object.keys(obj)[0]}": [`
  let nofblocks = subblocks.length;
  for (let i = 0; i < nofblocks; i++) {
    text = `${text} "${subblocks[i][0]}", ${JSON.stringify(subblocks[i][1])}`;
    if (i < nofblocks - 1) {
      text = `${text},\n`;
    }
  }
  return `${text}]`;
}

Blockly.LurawiKit['controls_if'] = function(block) {
  // If/elseif/else condition.
  var n = 0;
  var code = '[', branchCode, conditionCode;
  do {
    conditionCode = Blockly.LurawiKit.valueToCode(block, 'IF' + n,
        Blockly.LurawiKit.ORDER_NONE) || null;
    if (conditionCode) {
        if (n > 0) {
            code = code + ', "false_action": ';
        }
        branchCode = Blockly.LurawiKit.statementToCode(block, 'DO' + n) || '[]';
        code = code + conditionCode + concatenate_actions('{"true_action":['+branchCode+']}');
    }
    ++n;
  } while (block.getInput('IF' + n));

  if (block.getInput('ELSE')) {
    branchCode = Blockly.LurawiKit.statementToCode(block, 'ELSE') || [];
    code = code + ', ' + concatenate_actions('{"false_action":['+branchCode+']}');
  }
  n = 0;
  while (block.getInput('IF' + n)) {
    code = code + '}]';
    ++n;
  }
  code += ']';
  return code;
};

Blockly.LurawiKit['controls_ifelse'] = Blockly.LurawiKit['controls_if'];

Blockly.LurawiKit['logic_compare'] = function(block) {
    // Comparison operator.
    var OPERATORS = {
    'EQ': '=',
    'NEQ': '!=',
    'LT': '<',
    'LTE': '<=',
    'GT': '>',
    'GTE': '>='
    };
    var operator = OPERATORS[block.getFieldValue('OP')];
    var order = Blockly.LurawiKit.ORDER_RELATIONAL;
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'A', order) || '0';
    var argument1 = Blockly.LurawiKit.valueToCode(block, 'B', order) || '0';
    if (argument0[0] != '"') {
        argument0 = '"'+ argument0 + '"';
    }
    if (argument1[0] != '"') {
        argument1 = '"'+ argument1 + '"';
    }
    var code = '["compare", {"operand1": ' + argument0 + ', "operand2": ';
    code = code + argument1 + ', "comparison_operator": "' + operator + '",';
    return [code, order];
};

Blockly.LurawiKit['logic_negate'] = function(block) {
  // Negation.
  var argument0 = Blockly.LurawiKit.valueToCode(block, 'BOOL',
      Blockly.LurawiKit.ORDER_LOGICAL_NOT) || 'True';
  var code = 'not ' + argument0;
  return [code, Blockly.LurawiKit.ORDER_LOGICAL_NOT];
};

Blockly.LurawiKit['logic_boolean'] = function(block) {
  // Boolean values true and false.
  var code = (block.getFieldValue('BOOL') == 'TRUE') ? 'true' : 'false';
  return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};
