/**
 * @license

/**
 * @fileoverview Generating LurawiKit for variable blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

Blockly.LurawiKit['behaviour_action'] = function(block) {
    var parent = block.getSurroundParent();
    if (!parent) {
        return 'Orphan action block'
    }
    if (!(parent.type == "behaviour_behaviour" || parent.type.startsWith('control'))) {
        return 'Invalid, parent must be behaviour block.';
    }
    var statement = Blockly.LurawiKit.statementToCode(block, 'ACTIONLETS',
        Blockly.LurawiKit.ORDER_NONE) || '';
    var playnext_block = '\n';
    if (block.getFieldValue('PLAY_NEXT') == 'TRUE') {
        // check whether there is any existing play_behaviour child block
        /*
        var children = block.getDescendants();
        var clen = children.length;
        let hasplaybe = false;
        for (let i = 0; i < clen; i++) {
            if (children[i].type == 'play_behaviour_primitive') {
                hasplaybe = true;
                break;
            }
        }
        if (!hasplaybe) {
            playnext_block = ',\n["play_behaviour", "next"]\n';
        }
        */
        if (block.getNextBlock() || parent.type.startsWith('control')) {
            playnext_block = ',\n["play_behaviour", "next"]\n';
        }
    }
    var code = '[\n' + statement.slice(0,-1) + playnext_block + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['behaviour_chained_action'] = function(block) {
    var statement = Blockly.LurawiKit.statementToCode(block, 'ACTIONLETS',
        Blockly.LurawiKit.ORDER_NONE) || '';

    var code = statement.replace(/],\s*\[/g, ',') + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['behaviour_behaviour'] = function(block) {
    var namearg = block.getFieldValue('NAME') || 'default_behaviour';
    var isdefault = block.getFieldValue('IS_DEFAULT') || false;
    var statement = Blockly.LurawiKit.statementToCode(block, 'ACTIONS',
        Blockly.LurawiKit.ORDER_NONE) || '';

    if (isdefault == 'TRUE') {
        Blockly.LurawiKit.definitions_['default_behaviour'] = namearg;
    }

    Blockly.LurawiKit.definitions_['behaviours'].push(namearg);
    var nofbehaviours = Blockly.LurawiKit.definitions_['behaviours'].length;
    var code = (nofbehaviours > 1 ? ',\n' : '') + '{\n"name": "'+namearg+'",\n"actions": [\n' + statement + ']\n}';
    return code;
};
