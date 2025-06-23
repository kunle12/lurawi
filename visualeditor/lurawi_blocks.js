Blockly.Blocks['text_primitive'] = {
  init: function() {
    this.appendValueInput("VALUE")
        .setCheck("String")
        .appendField("say");
    this.setInputsInline(false);
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(210);
    this.setTooltip("enter a string of text for xbot to say to the user");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['respond_primitive'] = {
  init: function() {
    this.appendValueInput("STATUS")
        .setCheck("Number")
        .appendField("Respond with status code");
    this.appendValueInput("MESG")
        .setCheck("String")
        .appendField("message");
    this.appendDummyInput()
        .appendField("or")
    this.appendValueInput("PAYLOAD")
        .appendField("data");
    this.setInputsInline(false);
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(210);
    this.setTooltip("send http response to user");
    this.setHelpUrl("");
  }
};


Blockly.Blocks['delay_primitive'] = {
  init: function() {
    this.appendValueInput("VALUE")
        .setCheck("Number")
        .appendField("wait");
    this.appendDummyInput()
        .appendField("seconds");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
    this.setTooltip("enter wait in seconds (float)");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['bot_interaction_primitive'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("Agent interaction")
    this.appendStatementInput("ENGAGEMENT")
        .setAlign(Blockly.ALIGN_RIGHT)
        .setCheck(null)
        .appendField("when engage with a user");
    this.appendStatementInput("DISENGAGEMENT")
        .setAlign(Blockly.ALIGN_RIGHT)
        .setCheck(null)
        .appendField("after the user has left the conversation");
    this.appendStatementInput("USERDATA")
        .setAlign(Blockly.ALIGN_RIGHT)
        .setCheck(null)
        .appendField("when receives user data");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
    this.setTooltip("base bot interaction setup");
    this.setHelpUrl("");
    Blockly.Extensions.apply("bot_interaction_primitive_mutator", this, true);
  }
};

/**
 * Mixin for mutator functions in the 'custom_primitive_mutator'
 * extension.
 * @mixin
 * @augments Blockly.Block
 * @package
 */
var PEOPLE_TRACKER_PRIMITIVE_MUTATOR_MINXIN = {
    /**
    * Create XML to represent whether the 'divisorInput' should be present.
    * @return {Element} XML storage element.
    * @this Blockly.Block
    */
    mutationToDom: function() {
        var container = document.createElement('mutation');
        container.setAttribute('pt_status', this.getFieldValue('STATUS'));
        return container;
    },
    /**
    * Parse XML to restore the 'divisorInput'.
    * @param {!Element} xmlElement XML storage element.
    * @this Blockly.Block
    */
    domToMutation: function(xmlElement) {
        var ptstatus = xmlElement.getAttribute('pt_status');
        this.updateShape_(ptstatus);
    },
    /**
    * Modify this block to have (or not have) an input for 'is divisible by'.
    * @param {boolean} divisorInput True if this block has a divisor input.
    * @private
    * @this Blockly.Block
    */
    updateShape_: function(status) {
        if (status == 'OPTOFF') {
            Code.removeBotInteractionArgs(this);
        }
    }
};

Blockly.Extensions.registerMutator('bot_interaction_primitive_mutator',
    PEOPLE_TRACKER_PRIMITIVE_MUTATOR_MINXIN,
    null);

Blockly.Blocks['custom_primitive'] = {
  init: function() {
    this.appendDummyInput("SELECT_CUSTOM_SCRIPT")
        .setAlign(Blockly.ALIGN_RIGHT)
        .appendField("run function")
        .appendField(new Blockly.FieldDropdown([["",""]]), "SCRIPTS");
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
    this.setTooltip("Run a custom script with its associated arguments");
    this.setHelpUrl("");
    Blockly.Extensions.apply("custom_primitive_mutator", this, true);
  }
};

/**
 * Mixin for mutator functions in the 'custom_primitive_mutator'
 * extension.
 * @mixin
 * @augments Blockly.Block
 * @package
 */
var CUSTOM_PRIMITIVE_MUTATOR_MINXIN = {
    /**
    * Create XML to represent whether the 'divisorInput' should be present.
    * @return {Element} XML storage element.
    * @this Blockly.Block
    */
    mutationToDom: function() {
        var container = document.createElement('mutation');
        container.setAttribute('check_custom', this.getFieldValue('SCRIPTS'));
        return container;
    },
    /**
    * Parse XML to restore the 'divisorInput'.
    * @param {!Element} xmlElement XML storage element.
    * @this Blockly.Block
    */
    domToMutation: function(xmlElement) {
        var customScript = xmlElement.getAttribute('check_custom');
        this.updateShape_(customScript);
    },
    /**
    * Modify this block to have (or not have) an input for 'is divisible by'.
    * @param {boolean} divisorInput True if this block has a divisor input.
    * @private
    * @this Blockly.Block
    */
    updateShape_: function(customScript) {
        //console.log("custom script: " + customScript);
        let cs_names = Object.keys(Code.customScripts);
        if (cs_names.length > 0) {
            let fvalue = [];
            for (var v of cs_names) {
                fvalue.push([v, v]);
            }
            let fin = this.getInput('SELECT_CUSTOM_SCRIPT');
            fin.removeField('SCRIPTS');
            fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'SCRIPTS');
        }
        if (cs_names.indexOf(customScript) >= 0) {
            Code.addCustomScriptArgs(this, customScript);
        }
    }
};

Blockly.Extensions.registerMutator('custom_primitive_mutator',
    CUSTOM_PRIMITIVE_MUTATOR_MINXIN,
    null);

Blockly.Blocks['option_item_primitive'] = {
  init: function() {
    this.appendValueInput("OPTION")
        .setCheck("String")
        .appendField("keywords");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(230);
    this.setTooltip("Enter a list of comman separated keywords as an option");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['play_behaviour_primitive'] = {
  init: function() {
    this.appendDummyInput("SELECT_BEHAVIOUR")
        .appendField("play behaviour")
        .appendField(new Blockly.FieldDropdown([["",""]]), "BEHAVIOURS")
        .appendField("at index");
    this.appendDummyInput()
        .appendField(new Blockly.FieldNumber(0, 0), "ACTION_INDEX");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
    this.setTooltip("go to and play a behaviour");
    this.setHelpUrl("");
    Blockly.Extensions.apply("play_behaviour_primitive_mutator", this, true);
  }
};

/**
 * Mixin for mutator functions in the 'custom_primitive_mutator'
 * extension.
 * @mixin
 * @augments Blockly.Block
 * @package
 */
var PLAY_BEHAVIOUR_PRIMITIVE_MUTATOR_MINXIN = {
    /**
    * Create XML to represent whether the 'divisorInput' should be present.
    * @return {Element} XML storage element.
    * @this Blockly.Block
    */
    mutationToDom: function() {
        var container = document.createElement('mutation');
        container.setAttribute('existing_behaviours', Object.keys(Code.existingBehaviours).join());
        return container;
    },
    /**
    * Parse XML to restore the 'divisorInput'.
    * @param {!Element} xmlElement XML storage element.
    * @this Blockly.Block
    */
    domToMutation: function(xmlElement) {
        var belist = xmlElement.getAttribute('existing_behaviours').split(',');
        this.updateShape_(belist);
    },
    /**
    * Modify this block to have (or not have) an input for 'is divisible by'.
    * @param {boolean} divisorInput True if this block has a divisor input.
    * @private
    * @this Blockly.Block
    */
    updateShape_: function(be_names) {
        if (be_names.length > 0) {
            let fvalue = [];
            for (var v of be_names) {
                fvalue.push([v, v]);
                if (!(v in Code.existingBehaviours)) {
                  Code.existingBehaviours[v] = null;
                }
            }
            let fin = this.getInput('SELECT_BEHAVIOUR');
            fin.removeField('BEHAVIOURS');
            fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'BEHAVIOURS');
        }
        Code.existingPlayBehaviourActionLets.push(this);
    }
};

Blockly.Extensions.registerMutator('play_behaviour_primitive_mutator',
    PLAY_BEHAVIOUR_PRIMITIVE_MUTATOR_MINXIN,
    null);

Blockly.Blocks['select_behaviour_primitive'] = {
  init: function() {
    this.appendDummyInput("SELECT_BEHAVIOUR")
        .appendField("select behaviour")
        .appendField(new Blockly.FieldDropdown([["",""]]), "BEHAVIOURS")
        .appendField("at index");
    this.appendDummyInput()
        .appendField(new Blockly.FieldNumber(0, 0), "ACTION_INDEX");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
    this.setTooltip("go to a behaviour");
    this.setHelpUrl("");
    Blockly.Extensions.apply("select_behaviour_primitive_mutator", this, true);
  }
};

/**
 * Mixin for mutator functions in the 'custom_primitive_mutator'
 * extension.
 * @mixin
 * @augments Blockly.Block
 * @package
 */
var SELECT_BEHAVIOUR_PRIMITIVE_MUTATOR_MINXIN = {
    /**
    * Create XML to represent whether the 'divisorInput' should be present.
    * @return {Element} XML storage element.
    * @this Blockly.Block
    */
    mutationToDom: function() {
        var container = document.createElement('mutation');
        container.setAttribute('existing_behaviours', Object.keys(Code.existingBehaviours).join());
        return container;
    },
    /**
    * Parse XML to restore the 'divisorInput'.
    * @param {!Element} xmlElement XML storage element.
    * @this Blockly.Block
    */
    domToMutation: function(xmlElement) {
        var belist = xmlElement.getAttribute('existing_behaviours').split(',');
        this.updateShape_(belist);
    },
    /**
    * Modify this block to have (or not have) an input for 'is divisible by'.
    * @param {boolean} divisorInput True if this block has a divisor input.
    * @private
    * @this Blockly.Block
    */
    updateShape_: function(be_names) {
        if (be_names.length > 0) {
            let fvalue = [];
            for (var v of be_names) {
                fvalue.push([v, v]);
            }
            let fin = this.getInput('SELECT_BEHAVIOUR');
            fin.removeField('BEHAVIOURS');
            fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'BEHAVIOURS');
        }
        Code.existingPlayBehaviourActionLets.push(this);
    }
};

Blockly.Extensions.registerMutator('select_behaviour_primitive_mutator',
    SELECT_BEHAVIOUR_PRIMITIVE_MUTATOR_MINXIN,
    null);

Blockly.Blocks['play_next_primitive'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("play next action");
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(210);
  this.setTooltip("play next action in the behaviour");
  this.setHelpUrl("");
  }
};

Blockly.Blocks['behaviour_action'] = {
  init: function() {
    this.appendStatementInput("ACTIONLETS")
        .setCheck(null)
        .appendField("action");
    this.appendDummyInput()
        .appendField("continue")
        .appendField(new Blockly.FieldCheckbox("FALSE"), "PLAY_NEXT");
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(315);
    this.setTooltip("An action that is consist of a list of actionlets");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['behaviour_chained_action'] = {
  init: function() {
    this.appendStatementInput("ACTIONLETS")
        .setCheck(null)
        .appendField("chained actions");
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(335);
    this.setTooltip("Compose a single actionlet with multiple primitives that will executed in a consecutive sequence. NOTE: only one chained actions in an action!");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['behaviour_behaviour'] = {
  init: function() {
    this.appendDummyInput()
        .setAlign(Blockly.ALIGN_CENTRE)
        .appendField("default")
        .appendField(new Blockly.FieldCheckbox("FALSE"), "IS_DEFAULT")
        .appendField("behaviour")
        .appendField(new Blockly.FieldTextInput("__name__"), "NAME");
    this.appendStatementInput("ACTIONS")
        .setCheck(null)
        .setAlign(Blockly.ALIGN_RIGHT)
        .appendField("has");
    this.setInputsInline(false);
    this.setColour(135);
    this.setTooltip("insert a list of actions");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['key_value_store'] = {
  init: function() {
    this.appendValueInput("KEY")
        .setCheck("String")
        .appendField("key");
    this.appendValueInput("VALUE")
        .setCheck(null)
        .appendField("value");
    this.setInputsInline(true);
    this.setOutput("KeyValue");
    this.setColour(230);
    this.setTooltip("");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['key_action_store'] = {
  init: function() {
    this.appendValueInput("KEY")
        .setCheck("String")
        .appendField("key");
    this.appendStatementInput("ACTION")
        .setCheck(null)
        .appendField("action");
    this.setInputsInline(false);
    this.setOutput("KeyValue");
    this.setColour(230);
    this.setTooltip("");
    this.setHelpUrl("");
  }
};

Blockly.Blocks['dictionary_create_with'] = {
  /**
   * Block for creating a list with any number of elements of any type.
   * @this Blockly.Block
   */
  init: function() {
    this.setHelpUrl('');
    this.setColour(260);
    this.itemCount_ = 3;
    this.updateShape_();
    this.setOutput(true, 'Dictionary');
    this.setMutator(new Blockly.Mutator(['dictionary_create_with_item'], this));
    this.setTooltip('Create a dictionary with any number of key/value items.');
  },
  /**
   * Create XML to represent list inputs.
   * @return {!Element} XML storage element.
   * @this Blockly.Block
   */
  mutationToDom: function() {
    var container = document.createElement('mutation');
    container.setAttribute('items', this.itemCount_);
    return container;
  },
  /**
   * Parse XML to restore the list inputs.
   * @param {!Element} xmlElement XML storage element.
   * @this Blockly.Block
   */
  domToMutation: function(xmlElement) {
    this.itemCount_ = parseInt(xmlElement.getAttribute('items'), 10);
    this.updateShape_();
  },
  /**
   * Populate the mutator's dialog with this block's components.
   * @param {!Blockly.Workspace} workspace Mutator's workspace.
   * @return {!Blockly.Block} Root block in mutator.
   * @this Blockly.Block
   */
  decompose: function(workspace) {
    var containerBlock = workspace.newBlock('dictionary_create_with_container');
    containerBlock.initSvg();
    var connection = containerBlock.getInput('STACK').connection;
    for (var i = 0; i < this.itemCount_; i++) {
      var itemBlock = workspace.newBlock('dictionary_create_with_item');
      itemBlock.initSvg();
      connection.connect(itemBlock.previousConnection);
      connection = itemBlock.nextConnection;
    }
    return containerBlock;
  },
  /**
   * Reconfigure this block based on the mutator dialog's components.
   * @param {!Blockly.Block} containerBlock Root block in mutator.
   * @this Blockly.Block
   */
  compose: function(containerBlock) {
    var itemBlock = containerBlock.getInputTargetBlock('STACK');
    // Count number of inputs.
    var connections = [];
    while (itemBlock) {
      connections.push(itemBlock.valueConnection_);
      itemBlock = itemBlock.nextConnection &&
          itemBlock.nextConnection.targetBlock();
    }
    // Disconnect any children that don't belong.
    for (var i = 0; i < this.itemCount_; i++) {
      var connection = this.getInput('ADD' + i).connection.targetConnection;
      if (connection && connections.indexOf(connection) == -1) {
        connection.disconnect();
      }
    }
    this.itemCount_ = connections.length;
    this.updateShape_();
    // Reconnect any child blocks.
    for (var i = 0; i < this.itemCount_; i++) {
      Blockly.Mutator.reconnect(connections[i], this, 'ADD' + i);
    }
  },
  /**
   * Store pointers to any connected child blocks.
   * @param {!Blockly.Block} containerBlock Root block in mutator.
   * @this Blockly.Block
   */
  saveConnections: function(containerBlock) {
    var itemBlock = containerBlock.getInputTargetBlock('STACK');
    var i = 0;
    while (itemBlock) {
      var input = this.getInput('ADD' + i);
      itemBlock.valueConnection_ = input && input.connection.targetConnection;
      i++;
      itemBlock = itemBlock.nextConnection &&
          itemBlock.nextConnection.targetBlock();
    }
  },
  /**
   * Modify this block to have the correct number of inputs.
   * @private
   * @this Blockly.Block
   */
  updateShape_: function() {
    if (this.itemCount_ && this.getInput('EMPTY')) {
      this.removeInput('EMPTY');
    } else if (!this.itemCount_ && !this.getInput('EMPTY')) {
      this.appendDummyInput('EMPTY')
          .appendField('create an empty dictionary');
    }
    // Add new inputs.
    for (var i = 0; i < this.itemCount_; i++) {
      if (!this.getInput('ADD' + i)) {
        var input = this.appendValueInput('ADD' + i).setCheck("KeyValue");
        if (i == 0) {
          input.appendField('create dictionary with');
        }
      }
    }
    // Remove deleted inputs.
    while (this.getInput('ADD' + i)) {
      this.removeInput('ADD' + i);
      i++;
    }
  }
};

Blockly.Blocks['dictionary_create_with_container'] = {
  /**
   * Mutator block for list container.
   * @this Blockly.Block
   */
  init: function() {
    this.setColour(260);
    this.appendDummyInput()
        .appendField('dictionary');
    this.appendStatementInput('STACK');
    this.setTooltip('Add, remove, or reorder sections to reconfigure this dictionary block.');
    this.contextMenu = false;
  }
};

Blockly.Blocks['dictionary_create_with_item'] = {
  /**
   * Mutator block for adding items.
   * @this Blockly.Block
   */
  init: function() {
    this.setColour(260);
    this.appendDummyInput()
        .appendField('key/value item');
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Add a key/value item to the list.');
    this.contextMenu = false;
  }
};
