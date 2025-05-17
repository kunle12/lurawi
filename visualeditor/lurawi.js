/**
 * @fileoverview Helper functions for generating LurawiKit for blocks.
 * @author wang.xun@gmail.com
 */
'use strict';
/**
 * LurawiKit code generator.
 * @type {!Blockly.Generator}
 */
Blockly.LurawiKit = new Blockly.Generator('LurawiKit');

/**
 * List of illegal variable names.
 * This is not intended to be a security feature.  Blockly is 100% client-side,
 * so bypassing this list is trivial.  This is intended to prevent users from
 * accidentally clobbering a built-in object or function.
 * @private
 */
Blockly.LurawiKit.addReservedWords(
    'text,knowledge,web,delay,custom,' +
    'select_behaviour,play_behaviour,' +
    'random,calculate,compare,' +
    'comment, workflow_interaction'
);

/**
 * Order of operation ENUMs.
 * http://docs.python.org/reference/expressions.html#summary
 */
Blockly.LurawiKit.ORDER_ATOMIC = 0;            // 0 "" ...
Blockly.LurawiKit.ORDER_COLLECTION = 1;        // tuples, lists, dictionaries
Blockly.LurawiKit.ORDER_STRING_CONVERSION = 1; // `expression...`
Blockly.LurawiKit.ORDER_MEMBER = 2.1;          // . []
Blockly.LurawiKit.ORDER_FUNCTION_CALL = 2.2;   // ()
Blockly.LurawiKit.ORDER_UNARY_SIGN = 3;        // + -
Blockly.LurawiKit.ORDER_MULTIPLICATIVE = 4;    // * / // %
Blockly.LurawiKit.ORDER_ADDITIVE = 5;          // + -
Blockly.LurawiKit.ORDER_RELATIONAL = 6;       // in, not in, is, is not,
                                            //     <, <=, >, >=, <>, !=, ==
Blockly.LurawiKit.ORDER_LOGICAL_NOT = 7;      // not
Blockly.LurawiKit.ORDER_LOGICAL_AND = 8;      // and
Blockly.LurawiKit.ORDER_LOGICAL_OR = 9;       // or
Blockly.LurawiKit.ORDER_CONDITIONAL = 10;      // if else
Blockly.LurawiKit.ORDER_NONE = 99;             // (...)

/**
 * List of outer-inner pairings that do NOT require parentheses.
 * @type {!Array.<!Array.<number>>}
 */

/**
 * Initialise the database of variable names.
 * @param {!Blockly.Workspace} workspace Workspace to generate code from.
 */
Blockly.LurawiKit.init = function(workspace) {
  // Create a dictionary of definitions to be printed before the code.
  Blockly.LurawiKit.definitions_ = Object.create(null);
  // Create a dictionary mapping desired function names in definitions_
  // to actual function names (to avoid collisions with user functions).
  Blockly.LurawiKit.functionNames_ = Object.create(null);

  if (!Blockly.LurawiKit.nameDB_) {
    Blockly.LurawiKit.nameDB_ =
        new Blockly.Names(Blockly.LurawiKit.RESERVED_WORDS_);
  }
  else {
    Blockly.LurawiKit.nameDB_.reset();
  }

  Blockly.LurawiKit.nameDB_.setVariableMap(workspace.getVariableMap());

  var defvars = [];
  // Add developer variables (not created or named by the user).
  var devVarList = Blockly.Variables.allDeveloperVariables(workspace);
  for (var i = 0; i < devVarList.length; i++) {
    defvars.push(Blockly.LurawiKit.nameDB_.getName(devVarList[i],
        Blockly.Names.DEVELOPER_VARIABLE_TYPE) + ' = None');
  }

  // Add user variables, but only ones that are being used.
  var variables = Blockly.Variables.allUsedVarModels(workspace);
  for (var i = 0; i < variables.length; i++) {
    defvars.push('"'+Blockly.LurawiKit.nameDB_.getName(variables[i].getId(),
      Blockly.Names.NameType.VARIABLE).toUpperCase() + '": ""');
  }
  var cscripts = {};

  var codelib = document.getElementById('scriptlib');
  var x = codelib.getElementsByTagName("cscript");
  for (let i = 0; i < x.length; i++) {
      let cname = x[i].getAttribute('name');
      if (cname == '') continue;
      let cargs = [];
      let args = x[i].childNodes;
      let nofargs = args.length;
      for (let j = 0; j < nofargs; j++) {
          if (args[j].nodeName == 'ARGUMENT') {
              //console.log("arg type "+ args[j].getAttribute('type'));
              cargs.push([args[j].textContent,args[j].getAttribute('type')]);
          }
      }
      cscripts[cname] = cargs;
  }

  Blockly.LurawiKit.definitions_['variables'] = defvars;
  Blockly.LurawiKit.definitions_['custom_scripts'] = cscripts;
  Blockly.LurawiKit.definitions_['behaviours'] = [];
  Blockly.LurawiKit.definitions_['default_behaviour'] = null;
};

/**
 * Prepend the generated code with the variable definitions.
 * @param {string} code Generated code.
 * @return {string} Completed code.
 */
Blockly.LurawiKit.finish = function(code) {
  // Convert the definitions dictionary into a list.
  let code_warp = '';
  let init_be = '';

  if (Blockly.LurawiKit.definitions_['behaviours'].length > 0) {
      let defvars = Blockly.LurawiKit.definitions_['variables'];
      let def_be = Blockly.LurawiKit.definitions_['default_behaviour'];
      if (defvars.length > 0) {
          let kl_al = '["knowledge", {' + defvars + '}]';
          if (def_be) {
            let pn_al = '["play_behaviour", "'+ def_be+'"]'
            init_be = '{"name":"__init__", "actions":[['+kl_al+','+pn_al+']]},';
          }
          else {
            init_be = '{"name":"__init__", "actions":[['+kl_al+']]},';
          }
          Blockly.LurawiKit.definitions_['default_behaviour'] = "__init__";
      }
      if (Blockly.LurawiKit.definitions_['default_behaviour']) {
        code_warp = '{\n"default": "'+ Blockly.LurawiKit.definitions_['default_behaviour'] + '",\n"behaviours": [' + init_be+code + ']\n}'
      }
      else {
        code_warp = '{\n"behaviours": [' + init_be+code + ']\n}'
      }
  }
  else {
      code_warp = code;
  }
  //console.log(code_warp);
  // Clean up temporary data.
  delete Blockly.LurawiKit.definitions_;
  delete Blockly.LurawiKit.functionNames_;
  Blockly.LurawiKit.nameDB_.reset();
  return code_warp;
};

/**
 * Naked values are top-level blocks with outputs that aren't plugged into
 * anything.
 * @param {string} line Line of generated code.
 * @return {string} Legal line of code.
 */
Blockly.LurawiKit.scrubNakedValue = function(line) {
  return line + '\n';
};

/**
 * Encode a string as a properly escaped LurawiKit string, complete with quotes.
 * @param {string} string Text to encode.
 * @return {string} LurawiKit string.
 * @private
 */
Blockly.LurawiKit.quote_ = function(string) {
  // Can't use goog.string.quote since % must also be escaped.
  //string = string.replace(/\\/g, '\\\\')
  //               .replace(/\n/g, '\\\n');

  // Follow the LurawiKit behaviour of repr() for a non-byte string.
  var quote = '"';
  if (string.indexOf('"') !== -1) {
    string = string.replace(/["]/g, '\\\"');
  }

  if (string.indexOf('\'') !== -1) {
    if (string.indexOf('"') === -1) {
      quote = '"';
    } else {
      string = string.replace(/\\\'/g, "'");
    }
  };
  return quote + string + quote;
};

/**
 * Common tasks for generating LurawiKit from blocks.
 * Handles comments for the specified block and any connected value blocks.
 * Calls any statements following this block.
 * @param {!Blockly.Block} block The current block.
 * @param {string} code The LurawiKit code created for this block.
 * @return {string} LurawiKit code with comments and subsequent blocks added.
 * @private
 */
Blockly.LurawiKit.scrub_ = function(block, code) {
  var commentCode = '';
  // Only collect comments for blocks that aren't inline.
  if (!block.outputConnection || !block.outputConnection.targetConnection) {
    // Collect comment for this block.
    var comment = block.getCommentText();
    if (comment) {
        if (block.type == 'behaviour_action') {
            commentCode += '[["comment": "' + comment + '"], ["play_behaviour", "next"]],\n';
        }
        else {
            commentCode += '["comment": "' + comment + '"],\n';
        }
    }
    // Collect comments for all value arguments.
    // Don't collect comments for nested statements.
    for (var i = 0; i < block.inputList.length; i++) {
      if (block.inputList[i].type == Blockly.INPUT_VALUE) {
        var childBlock = block.inputList[i].connection.targetBlock();
        if (childBlock) {
          var comment = Blockly.LurawiKit.allNestedComments(childBlock);
          if (comment) {
              commentCode += '["comment": "' + comment + '"],\n';
          }
        }
      }
    }
  }
  var nextBlock = block.nextConnection && block.nextConnection.targetBlock();
  var nextCode = Blockly.LurawiKit.blockToCode(nextBlock);
  return commentCode + code + nextCode;
};

/**
 * Gets a property and adjusts the value, taking into account indexing, and
 * casts to an integer.
 * @param {!Blockly.Block} block The block.
 * @param {string} atId The property ID of the element to get.
 * @param {number=} opt_delta Value to add.
 * @param {boolean=} opt_negate Whether to negate the value.
 * @return {string|number}
 */
Blockly.LurawiKit.getAdjustedInt = function(block, atId, opt_delta, opt_negate) {
  var delta = opt_delta || 0;
  if (block.workspace.options.oneBasedIndex) {
    delta--;
  }
  var defaultAtIndex = block.workspace.options.oneBasedIndex ? '1' : '0';
  var atOrder = delta ? Blockly.LurawiKit.ORDER_ADDITIVE :
      Blockly.LurawiKit.ORDER_NONE;
  var at = Blockly.LurawiKit.valueToCode(block, atId, atOrder) || defaultAtIndex;

  if (Blockly.utils.string.isNumber(at)) {
    // If the index is a naked number, adjust it right now.
    at = parseInt(at, 10) + delta;
    if (opt_negate) {
      at = -at;
    }
  } else {
    // If the index is dynamic, adjust it in code.
    if (delta > 0) {
      at = 'int(' + at + ' + ' + delta + ')';
    } else if (delta < 0) {
      at = 'int(' + at + ' - ' + -delta + ')';
    } else {
      at = 'int(' + at + ')';
    }
    if (opt_negate) {
      at = '-' + at;
    }
  }
  return at;
};
