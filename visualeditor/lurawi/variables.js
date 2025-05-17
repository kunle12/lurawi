/**
 * @license

/**
 * @fileoverview Generating LurawiKit for variable blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

Blockly.LurawiKit['variables_get'] = function(block) {
    // Variable getter.
    var code = Blockly.LurawiKit.nameDB_.getName(block.getFieldValue('VAR'),
        Blockly.Names.NameType.VARIABLE).toUpperCase();

    code = '"' + code + '"';

    return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};

Blockly.LurawiKit['variables_set'] = function(block) {
    // Variable setter.
    var code = '';
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'VALUE',
        Blockly.LurawiKit.ORDER_NONE) || '0';

    var varName = Blockly.LurawiKit.nameDB_.getName(block.getFieldValue('VAR'),
        Blockly.Names.NameType.VARIABLE).toUpperCase();

    if (typeof argument0 == 'string' && argument0.startsWith('calculate:')) {
        let arg = argument0.split(':')[1];
        arg = arg.replace(/"/g, '');
        code = '["calculate", ["'+ varName + '", "' + arg + '"]]';
    }
    else {
        code = '["knowledge", {"' + varName + '" : ' + argument0 + '}]';
    }
    return code + (block.getNextBlock() ? ',\n' : '\n');
};
