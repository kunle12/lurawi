/**
 * @license

/**
 * @fileoverview Generating LurawiKit for variable blocks.
 * @author wang.xun@gmail.com
 */
'use strict';

Blockly.LurawiKit['text_primitive'] = function(block) {
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'VALUE',
        Blockly.LurawiKit.ORDER_NONE) || '""';

    var code = '["text", ' + argument0 + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['respond_primitive'] = function(block) {
    var argument0 = Blockly.LurawiKit.valueToCode(block, 'STATUS',
        Blockly.LurawiKit.ORDER_NONE) || '200';
    var message = Blockly.LurawiKit.valueToCode(block, 'MESG',
        Blockly.LurawiKit.ORDER_NONE) || '""';
    var payload = Blockly.LurawiKit.valueToCode(block, 'PAYLOAD',
        Blockly.LurawiKit.ORDER_NONE) || '""';

    let code = ''
    if (payload !== '""') {
        console.log("got here");
        try {
            let _ = JSON.parse(payload)
        } catch (e) {
            console.log("respond_primitive: payload is not a dict")
            return null
        }
        code = '["http_response", { "status_code": ' + argument0 + ', ' + payload.replace(/^{?/, '') + ' ]' + (block.getNextBlock() ? ',\n' : '\n');
    }
    else if (message !== '""') {
        code = '["http_response", { "status_code": ' + argument0 + ', "message": ' + message + ' }]' + (block.getNextBlock() ? ',\n' : '\n');
    }
    return code;
};

Blockly.LurawiKit['bot_interaction_primitive'] = function(block) {
    var engage_action = null;
    var disengage_action = null;
    var userdata_action = null;
    var actionargs = '';

    engage_action = Blockly.LurawiKit.statementToCode(block, 'ENGAGEMENT',
        Blockly.LurawiKit.ORDER_NONE) || null;
    disengage_action = Blockly.LurawiKit.statementToCode(block, 'DISENGAGEMENT',
        Blockly.LurawiKit.ORDER_NONE) || null;
    userdata_action = Blockly.LurawiKit.statementToCode(block, 'USERDATA',
        Blockly.LurawiKit.ORDER_NONE) || null;
    let args = []
    if (engage_action) {
        args.push('"engagement": ' + engage_action.replace(/],\s*\[/g, ','));
    }
    if (disengage_action) {
        args.push('"disengagement": ' + disengage_action.replace(/],\s*\[/g, ','));
    }
    if (userdata_action) {
        args.push('"userdata": ' + userdata_action.replace(/],\s*\[/g, ','));
    }
    if (args.length > 0) {
        actionargs = '["workflow_interaction", {' + args.join() + '}]';
    }

    var code = actionargs + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['custom_primitive'] = function(block) {
    var cscript = block.getFieldValue('SCRIPTS') || 'selfie' // why?;
    var cargs = Blockly.LurawiKit.definitions_['custom_scripts'][cscript];
    var nofargs = cargs.length;

    var args = '';

    var nofvalidargs = 0;
    for (let i = 0; i < nofargs; i++) {
        let arg = cargs[i];
        let value = '""';
        if (arg[1] === 'action') {
            value = Blockly.LurawiKit.statementToCode(block, 'ARG'+i,
                Blockly.LurawiKit.ORDER_NONE) || null;
        }
        else {
            value = Blockly.LurawiKit.valueToCode(block, 'ARG'+i,
                Blockly.LurawiKit.ORDER_NONE) || '""';
        }
        if (value !== '""' && value !== null) {
            nofvalidargs++;
        }
    }

    if (nofvalidargs > 0) {
        let vargcnt = 0;
        args = '{"name" : "' + cscript + '", "args": {';
        for (let i = 0; i < nofargs; i++) {
            let arg = cargs[i];
            let value = '""';
            if (arg[1] === 'action') {
                value = Blockly.LurawiKit.statementToCode(block, 'ARG'+i,
                    Blockly.LurawiKit.ORDER_NONE) || null;
                if (value) {
                    if (arg[0].endsWith('actions')) {
                        value = '['+ value +']';
                    }
                    else { // this additional check is really bad hack for options
                        value = value.replace(/],\s*\[/g, ',');
                    }
                }
            }
            else {
                value = Blockly.LurawiKit.valueToCode(block, 'ARG'+i,
                    Blockly.LurawiKit.ORDER_NONE) || '""';
            }
            if (value !== '""' && value !== null) {
                vargcnt++;
                args = args + '"' + arg[0] + '": ' + value;
                if (vargcnt < nofvalidargs) {
                    args = args + ',\n';
                }
                else {
                    args = args + '}';
                }
            }
        }
        args = args + "}";
    }
    else {
        args = '"' + cscript + '"';
    }
    var code = '["custom", ' + args + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['play_behaviour_primitive'] = function(block) {
    var arg_be = block.getFieldValue('BEHAVIOURS') || '';
    var arg_inx = block.getFieldValue('ACTION_INDEX') || 0;

    var arg = arg_be == '' ? '"' + arg_inx + '"' : '"' + arg_be + ':' + arg_inx + '"'
    var code = '["play_behaviour", ' + arg + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['select_behaviour_primitive'] = function(block) {
    var arg_be = block.getFieldValue('BEHAVIOURS') || '';
    var arg_inx = block.getFieldValue('ACTION_INDEX') || 0;

    var arg = arg_be == '' ? '"' + arg_inx + '"' : '"' + arg_be + ':' + arg_inx + '"'
    var code = '["select_behaviour", ' + arg + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['play_next_primitive'] = function(block) {
    var code = '["play_behaviour", "next"]' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['delay_primitive'] = function(block) {
    var delay = Blockly.LurawiKit.valueToCode(block, 'VALUE',
        Blockly.LurawiKit.ORDER_NONE) || 0;
    var code = '["delay", '+ delay + ']' + (block.getNextBlock() ? ',\n' : '\n');
    return code;
};

Blockly.LurawiKit['key_value_store'] = function(block) {
    var key = Blockly.LurawiKit.valueToCode(block, 'KEY',
        Blockly.LurawiKit.ORDER_NONE) || '""';

    var value = Blockly.LurawiKit.valueToCode(block, 'VALUE',
        Blockly.LurawiKit.ORDER_NONE) || '""';

    if (key[0] != '"') {
        key = '"'+ key + '"';
    }

    if (!(value[0] == '{' || value[0] == '[' || value[0] == '"')) {
        value = '"'+ value + '"';
    }
    var code = key + ": " + value + (block.getNextBlock() ? ',\n' : '\n');
    return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};

Blockly.LurawiKit['key_action_store'] = function(block) {
    var key = Blockly.LurawiKit.valueToCode(block, 'KEY',
        Blockly.LurawiKit.ORDER_NONE) || '""';

    var action = Blockly.LurawiKit.statementToCode(block, 'ACTION',
        Blockly.LurawiKit.ORDER_NONE) || '[]';

    if (key[0] != '"') {
        key = '"'+ key + '"';
    }

    action = action.replace(/],\s*\[/g, ',');

    var code = key + ": " + action + (block.getNextBlock() ? ',\n' : '\n');
    return [code, Blockly.LurawiKit.ORDER_ATOMIC];
};
