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
 * @fileoverview Generating LurawiKit for list blocks.
 * @author q.neutron@gmail.com (Quynh Neutron)
 */
'use strict';

Blockly.LurawiKit['dictionary_create_empty'] = function(block) {
  // Create an empty list.
  return ['{}', Blockly.LurawiKit.ORDER_ATOMIC];
};

Blockly.LurawiKit['dictionary_create_with'] = function(block) {
  // Create a list with any number of elements of any type.
  var elements = new Array(block.itemCount_);
  for (var i = 0; i < block.itemCount_; i++) {
    elements[i] = Blockly.LurawiKit.valueToCode(block, 'ADD' + i,
        Blockly.LurawiKit.ORDER_NONE) || 'None';
  }
  var code = '{' + elements.join(', ') + '}';
  return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};
