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
 * @fileoverview Generating LurawiKit for loop blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

Blockly.LurawiKit['controls_repeat_ext'] = function(block) {
    // Repeat n times.
    var repeats = 0;
    var fromIdx = 0;
    if (block.getField('TIMES')) {
    // Internal number.
        repeats = String(parseInt(block.getFieldValue('TIMES'), 10));
    }
    else {
        // External number.
        repeats = Blockly.LurawiKit.valueToCode(block, 'TIMES',
            Blockly.LurawiKit.ORDER_NONE) || '0';
    }
    if (Blockly.utils.string.isNumber(repeats)) {
        repeats = parseInt(repeats, 10);
    }
    else {
      return '';
    }
    var parent = block.getSurroundParent();
    var nextBlock = parent.getChildren()[0];
    while (nextBlock != block) {
        nextBlock = nextBlock.getNextBlock();
        fromIdx++;
    }

    // use the last action in the control loop to determine if we
    // want to continue to the next block after the loop.
    var continue_after = false;
    if (block.getChildren().length > 1) { // include count field as a children
        var pb = block.getChildren()[1];
        var nb = pb;
        while (nb) {
            pb = nb;
            nb = nb.getNextBlock();
        }
        continue_after = (pb.getFieldValue('PLAY_NEXT') == 'TRUE' && block.getNextBlock());
    }
    var branch = Blockly.LurawiKit.statementToCode(block, 'DO');
    var code = '[["knowledge", {"__COUNT__" : 1}], ["play_behaviour", "next"]],';
    code = code + branch + ',[["compare", {"operand1": "__COUNT__", "operand2" : "' + repeats + '",';
    code = code + '"comparison_operator": "<", "true_action" : ["calculate", ["__COUNT__", "__COUNT__ + 1"], "play_behaviour", "' + ++fromIdx +'"]';
    code = code + (continue_after ? ',"false_action" : ["play_behaviour", "next"]' : '') + '}]]';
    return code + (block.getNextBlock() ? ',\n' : '\n');
};

Blockly.LurawiKit['controls_repeat'] = Blockly.LurawiKit['controls_repeat_ext'];

Blockly.LurawiKit['controls_whileUntil'] = function(block) {
    // Do while/until loop.
    var fromIdx = 0;
    var code = '';

    var until = block.getFieldValue('MODE') == 'UNTIL';
    var conditionCode = Blockly.LurawiKit.valueToCode(block, 'BOOL',
        Blockly.LurawiKit.ORDER_NONE) || null;

    var parent = block.getSurroundParent();
    var nextBlock = parent.getChildren()[0];
    while (nextBlock != block) {
      nextBlock = nextBlock.getNextBlock();
      fromIdx++;
    }

    // use the last action in the control loop to determine if we
    // want to continue to the next block after the loop.
    var continue_after = false;
    var noc = 1;
    //console.log("children " + block.getChildren().length);
    if (block.getChildren().length > 1) { // include count field as a children
      var pb = block.getChildren()[1];
      var nb = pb;
      while (nb) {
          pb = nb;
          nb = nb.getNextBlock();
          noc++;
      }
      continue_after = (pb.getFieldValue('PLAY_NEXT') == 'TRUE' && block.getNextBlock());
    }

    if (conditionCode) {
        var branch = Blockly.LurawiKit.statementToCode(block, 'DO');
        if (until) {
            code = code + branch + ',[' + conditionCode;
            code = code + (continue_after ? '"true_action" : ["play_behaviour", "next"],' : '');
            code = code + '"false_action": ["play_behaviour", "' + fromIdx +'"]}]]';
        }
        else {
            code = code + '[' + conditionCode + '"true_action" : ["play_behaviour", "next"]';
            code = code + (continue_after ? ',"false_action" : ["play_behaviour", "' + (noc + fromIdx + 1) + '"]' : '');
            code = code + '}]],' + branch + ',[' + conditionCode;
            code = code + '"true_action": ["play_behaviour", "' + (fromIdx + 1) +'"]';
            code = code + (continue_after ? ',"false_action" : ["play_behaviour", "next"]' : '') + '}]]';
        }
    }

    return code + (block.getNextBlock() ? ',\n' : '\n');
};

Blockly.LurawiKit['controls_for'] = function(block) {
    // For loop.
    var fromIdx = 0;

    var variable0 = Blockly.LurawiKit.nameDB_.getName(
      block.getFieldValue('VAR'), Blockly.Names.NameType.VARIABLE);
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'FROM',
      Blockly.LurawiKit.ORDER_NONE) || '0';
    var argument1 = Blockly.LurawiKit.valueToCode(block, 'TO',
      Blockly.LurawiKit.ORDER_NONE) || '0';
    var increment = Blockly.LurawiKit.valueToCode(block, 'BY',
      Blockly.LurawiKit.ORDER_NONE) || '1';

    if (!Blockly.utils.string.isNumber(argument0) || !Blockly.utils.string.isNumber(argument1) || !Blockly.utils.string.isNumber(increment)) {
        return '';
    }

    variable0 = variable0.toUpperCase();
    var start = parseInt(argument0, 10);
    var end = parseInt(argument1, 10);
    var inc = parseInt(increment, 10);

    if ((end - start) < inc) {
        console.log('invalid control_for input');
        return '';
    }
    var parent = block.getSurroundParent();
    var nextBlock = parent.getChildren()[0];
    while (nextBlock != block) {
      nextBlock = nextBlock.getNextBlock();
      fromIdx++;
    }

    // use the last action in the control loop to determine if we
    // want to continue to the next block after the loop.
    var continue_after = false;
    console.log("children " + block.getChildren().length);
    if (block.getChildren().length > 3) { // include count field as a children
      var pb = block.getChildren()[3];
      var nb = pb;
      while (nb) {
          pb = nb;
          nb = nb.getNextBlock();
      }
      continue_after = (pb.getFieldValue('PLAY_NEXT') == 'TRUE' && block.getNextBlock());
    }
    var branch = Blockly.LurawiKit.statementToCode(block, 'DO');
    var code = '[["knowledge", {"' + variable0 + '" : ' + start + '}], ["play_behaviour", "next"]],';
    code = code + branch + ',[["calculate", ["' + variable0 + '", "' + variable0 + ' + ' + inc + '"]],';
    code = code + '["compare", {"operand1": "' + variable0 + '", "operand2" : "' + end + '",';
    code = code + '"comparison_operator": "<=", "true_action" : ["play_behaviour", "' + ++fromIdx +'"]';
    code = code + (continue_after ? ',"false_action" : ["play_behaviour", "next"]' : '') + '}]]';
    return code + (block.getNextBlock() ? ',\n' : '\n');
};
