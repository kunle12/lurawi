'use strict';

/**
 * Create a namespace for the application.
 */
/**
* Compute the absolute coordinates and dimensions of an HTML element.
* @param {!Element} element Element to match.
* @return {!Object} Contains height, width, x, and y properties.
* @private
*/
function getBBox(element) {
    var height = element.offsetHeight;
    var width = element.offsetWidth;
    var x = 0;
    var y = 0;
    do {
        x += element.offsetLeft;
        y += element.offsetTop;
        element = element.offsetParent;
    } while (element);
    return {
                height: height,
                width: width,
                x: x,
                y: y
            };
};

const plugin = new CrossTabCopyPaste();
plugin.init();

var Code = {
    options: {
        toolbox : null,
        collapse : true,
        comments : true,
        disable : true,
        maxBlocks : Infinity,
        trashcan : true,
        horizontalLayout : false,
        toolboxPosition : 'start',
        css : true,
        media : 'blockly/media/',
        rtl : false,
        scrollbars : true,
        sounds : true,
        oneBasedIndex : true,
        grid : {
          spacing : 20,
          length : 1,
          colour : '#888',
          snap : true
        },
        zoom : {
          controls : true,
          wheel : true,
          startScale : 1,
          maxScale : 3,
          minScale : 0.3,
          scaleSpeed : 1.2
        },
        plugins: {
            ...plugin,
        }
    },
    TABS_ : ['blocks', 'lurawi'],
    existingBehaviours : {},
    nextBehaviourId : 0,
    existingPlayBehaviorActionLets : [],
    customScripts: {},
    defaultMotions: [],

    onresize: function(e) {
        var bBox = getBBox(Code.container);
        for (let i = 0; i < Code.TABS_.length; i++) {
            var el = document.getElementById('content_' + Code.TABS_[i]);
            el.style.top = bBox.y + 'px';
            el.style.left = bBox.x + 'px';
            // Height and width need to be set, read back, then set again to
            // compensate for scrollbars.
            el.style.height = bBox.height + 'px';
            el.style.height = (2 * bBox.height - el.offsetHeight) + 'px';
            el.style.width = bBox.width + 'px';
            el.style.width = (2 * bBox.width - el.offsetWidth) + 'px';
        }
        // Make the 'Blocks' tab line up with the toolbox.
        if (Code.workspace && Code.workspace.toolbox_.width) {
            document.getElementById('tab_blocks').style.minWidth =
              (Code.workspace.toolbox_.width - 38) + 'px';
              // Account for the 19 pixel margin and on each side.
        }
    },
    handleLoadFile: function(event) {
        let files = event.target.files; // FileList object
        if (files.length != 1) {
            return;
        }
        var reader = new FileReader();

        // Closure to capture the file information.
        reader.onload = (function(e) {
            var text = reader.result;
            //console.log( "content " + text);
            try {
                let xml = Blockly.utils.xml.textToDom(text);
                Blockly.Xml.domToWorkspace(xml, Code.workspace);
            }
            catch (e) {
              let message = 'Could not load your block file.\n'
              alert(message + '\nFile Name: ' + file[0].name);
              return;
            }
            Code.loadFile.value = '';
        });
        console.log("load file " + files[0].name);
        // Read in the image file as a data URL.
        //Code.workspace.clear();
        reader.readAsText(files[0]);
    },
    createAndDownloadFile: function(contents, filename, fileType) {
        var data = new Blob([contents], {type: 'text/' + fileType});
        var clickEvent = new MouseEvent("click", {
        "view": window,
        "bubbles": true,
        "cancelable": false
        });

        var a = document.createElement('a');
        a.href = window.URL.createObjectURL(data);
        a.download = filename;
        a.textContent = 'Download file!';
        a.dispatchEvent(clickEvent);
    },
    handleSaveFile: function(event) {
        if (Code.selected == 'blocks') {
            var filename = prompt('Enter the file name under which to save your workflow blocks', 'lurawi_workflow.xml');
            // Download file if all necessary parameters are provided.
            if (filename) {
                let xml = Blockly.Xml.workspaceToDom(Code.workspace);
                let xml_text = Blockly.Xml.domToPrettyText(xml);
                //console.log('save data ' + xml_text);
                Code.createAndDownloadFile(xml_text, filename, 'xml');
            }
        }
        else {
            var filename = prompt('Enter the file name under which to save the lurawi json code', 'lurawi_code.json');
            // Download file if all necessary parameters are provided.
            if (filename) {
                let content = document.getElementById('content_' + Code.selected);
                Code.createAndDownloadFile(content.textContent, filename, 'json');
            }
        }
    },
    dispatchToServer: function(str) {
        const url = "http://localhost:8081/codeupdate"
        const payload_dict = {
            "jsonCode": str,
        }
        let payload = JSON.stringify(payload_dict)
        const postOptions = {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: payload
        }
        fetch(url, postOptions).then(
            response => response.json().then(
                (result) => {
                    if (result['status'] == 'success') {
                        alert("successfully uploaded code to the development server.")
                    }
                    else {
                        alert("failed to uploaded code to the development server.")
                    }
                }
            )
        )
        .catch((error) => {
            alert("failed to uploaded code to the development server.")
        })
    },
    handleSendFile: function(event) {
        if (Code.selected == 'blocks') {
            let code = ""
            try {
                code = Blockly.LurawiKit.workspaceToCode(Code.workspace);
            }
            catch(error) {
                alert("Unable to generate json code, visual code block is invalid.")
                return
            }
            if (code) {
                try {
                    code = JSON.parse(code);
                }
                catch(error) {
                    alert("Unable to send to the development server, visual code block is invalid.")
                }
                finally {
                    Code.dispatchToServer(JSON.stringify(code))
                }
            }
            else {
                alert("No code to be uploaded to the development server.")
            }
        }
        else {
            let code = document.getElementById('content_' + Code.selected).textContent
            if (code.startsWith("Invalid")) {
                alert("Unable to send to the development server, visual code block is invalid.")
            }
            else if (code.startsWith('Build')) {
                alert("No code to be uploaded to the development server.")
            }
            else {
                Code.dispatchToServer(code)
            }
        }
    },
    openTestConsole: function(event) {
        let d = window.open('http://localhost:3031/invokellm.html?smooth=true', 'Lurawi Test Console', 'noopener=yes');
    },
    openDocumatation: function(event) {
        let d = window.open('http://localhost:3031/doc_html/index.html', 'Lurawi Documetation', 'noopener=yes');
    },
    addBotInteractionArgs: function(block, cscript) {
        block.appendStatementInput("ENGAGEMENT").setCheck(null).setAlign(Blockly.ALIGN_RIGHT).appendField('when engage with a person');
        block.appendStatementInput("DISENGAGEMENT").setCheck(null).setAlign(Blockly.ALIGN_RIGHT).appendField('after the person has left');
        block.appendStatementInput("USERDATA").setCheck(null).setAlign(Blockly.ALIGN_RIGHT).appendField('when receives user data');
    },
    removeBotInteractionArgs: function(block) {
        block.removeInput("DISENGAGEMENT");
        block.removeInput("ENGAGEMENT");
        block.removeInput("USERDATA");
    },
    addCustomScriptArgs: function(block, cscript) {
        let ocsargs = Code.customScripts[cscript]
        let nofargs = ocsargs.length;
        if (nofargs > 0) {
            let fin = block.getInput('SELECT_CUSTOM_SCRIPT');
            fin.insertFieldAt(2, "with", 'WITH');
            for (let i = 0; i < nofargs; i++) {
                let arg = ocsargs[i];
                if (arg[1] == 'action') { // create statement input
                    block.appendStatementInput("ARG"+i).setCheck(null).setAlign(Blockly.ALIGN_RIGHT).appendField(arg[0]);
                }
                else {
                    let chktype = null;
                    if (arg[1] == 'boolean')
                        chktype = "Boolean";
                    else if (arg[1] == 'string')
                        chktype = "String";
                    else if (arg[1] == 'number')
                        chktype = "Number";
                    block.appendValueInput("ARG"+i).setCheck(chktype).setAlign(Blockly.ALIGN_RIGHT).appendField(arg[0]);
                }
            }
        }
    },
    removeCustomScriptArgs: function(block, cscript) {
        let ocsargs = Code.customScripts[cscript]
        let nofargs = ocsargs.length;
        if (nofargs > 0) {
            let fin = block.getInput('SELECT_CUSTOM_SCRIPT');
            fin.removeField('WITH');
            for (let i = 0; i < nofargs; i++) {
                block.removeInput("ARG"+i);
            }
        }
    },
    blockEvent: function(event) {
        if (event.type == Blockly.Events.BLOCK_CREATE) {
            let block = Code.workspace.getBlockById(event.blockId);
            if (block.type == 'behaviour_behaviour') {
                let name = block.getFieldValue('NAME');
                let be_names = Object.keys(Code.existingBehaviours);
                if (name == '__name__' || Code.existingBehaviours[name]) {
                    if (Code.nextBehaviourId <= be_names.length) {
                        Code.nextBehaviourId = be_names.length;
                    }

                    name = 'be'+ (++Code.nextBehaviourId);
                    block.setFieldValue(name, 'NAME');
                    be_names.push(name);
                }
                else {
                    Code.existingBehaviours[name] = block;
                }
                for (var pba of Code.existingPlayBehaviorActionLets) {
                    let fvalue = [];
                    for (var v of be_names) {
                        fvalue.push([v, v]);
                    }
                    let fin = pba.getInput('SELECT_BEHAVIOUR');
                    let selected_be = pba.getFieldValue('BEHAVIOURS');
                    let newbel = new Blockly.FieldDropdown(fvalue);
                    newbel.setValue(selected_be);
                    fin.removeField('BEHAVIOURS');
                    fin.insertFieldAt(1, newbel, 'BEHAVIOURS');
                }
            }
            else if (block.type == 'custom_primitive') {
                let cs_names = Object.keys(Code.customScripts);
                if (cs_names.length > 0) {
                    let fvalue = [];
                    for (var v of cs_names) {
                        fvalue.push([v, v]);
                    }
                    let fin = block.getInput('SELECT_CUSTOM_SCRIPT');
                    fin.removeField('SCRIPTS');
                    fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'SCRIPTS');
                    Code.addCustomScriptArgs(block, cs_names[0]);
                }
            }
            else if (block.type == 'default_motion_primitive') {
                if (Code.defaultMotions.length > 0) {
                    let fvalue = [];
                    for (var v of Code.defaultMotions) {
                        fvalue.push([v[0], v[0]]);
                    }
                    let fin = block.getInput('SELECT_DEFAULT_MOTION');
                    fin.removeField('VALUE');
                    fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'VALUE');
                }
            }
            else if (block.type == 'play_behaviour_primitive' || block.type == 'select_behaviour_primitive') {
                let be_names = Object.keys(Code.existingBehaviours);
                if (be_names.length > 0) {
                    let fvalue = [];
                    for (var v of be_names) {
                        fvalue.push([v, v]);
                    }
                    let fin = block.getInput('SELECT_BEHAVIOUR');
                    fin.removeField('BEHAVIOURS');
                    fin.insertFieldAt(1, new Blockly.FieldDropdown(fvalue), 'BEHAVIOURS');
                }
            }
        }
        else if (event.type == Blockly.Events.BLOCK_CHANGE) {
            let block = Code.workspace.getBlockById(event.blockId);
            if (block.type == 'behaviour_behaviour') {
                //console.log( "block change event name "+ event.name + " value " + event.newValue);
                if (event.name == 'NAME') {
                    //console.log( "change be name from " + event.oldValue + " to " + event.newValue);
                    if (event.oldValue == "__name__" || event.oldValue in Code.existingBehaviours) {
                        if (event.newValue in Code.existingBehaviours) {
                            alert("Behaviour name change: there is an existing behaviour with name "+event.newValue);
                            block.setFieldValue(event.oldValue, 'NAME'); // reset the behaviour name
                            return;
                        }
                        if (event.oldValue != "__name__" && Code.existingBehaviours[event.oldValue] == block) {
                            delete Code.existingBehaviours[event.oldValue];
                        }
                        Code.existingBehaviours[event.newValue] = block;
                        let be_names = Object.keys(Code.existingBehaviours);

                        for (var pba of Code.existingPlayBehaviorActionLets) {
                            let fvalue = [['','']];
                            for (var v of be_names) {
                                fvalue.push([v, v]);
                            }
                            let fin = pba.getInput('SELECT_BEHAVIOUR');
                            let selected_be = pba.getFieldValue('BEHAVIOURS');
                            if (selected_be == event.oldValue && Code.existingBehaviours[event.oldValue] == block) {
                                selected_be = event.newValue;
                            }
                            let newbel = new Blockly.FieldDropdown(fvalue);
                            newbel.setValue(selected_be);
                            fin.removeField('BEHAVIOURS');
                            fin.insertFieldAt(1, newbel, 'BEHAVIOURS');
                        }
                    }
                }
                else if (event.name == "IS_DEFAULT" && event.newValue == true) {
                    let be_names = Object.keys(Code.existingBehaviours);
                    for (var v of be_names) {
                        if (Code.existingBehaviours[v].id != event.blockId) {
                            Code.existingBehaviours[v].setFieldValue("FALSE", "IS_DEFAULT");
                        }
                    }
                }
            }
            else if (block.type == 'custom_primitive') {
                if (event.name == 'SCRIPTS') {
                    //console.log("changing from " + event.oldValue + " to " + event.newValue);
                    Code.removeCustomScriptArgs(block, event.oldValue);
                    Code.addCustomScriptArgs(block, event.newValue);
                }
            }
            else if (block.type == 'bot_interaction_primitive') {
                if (event.name == 'STATUS') {
                    if (event.newValue == 'OPTOFF') {
                        Code.removeBotInteractionArgs(block);
                    }
                    else {
                        Code.addBotInteractionArgs(block);
                    }
                }
            }
        }
        else if (event.type == Blockly.Events.BLOCK_MOVE) {
            let block = Code.workspace.getBlockById(event.blockId);
            if (!block) return;
            if (block.type == 'behaviour_chained_action') {
                if (!event.newParentId) {
                    return;
                }
                let parent = block.getSurroundParent();
                if (!(parent.type == "behaviour_action" || parent.type.endsWith('primitive'))) {
                    alert('Chained actionlet can only be attached directly to the action. UNDO your last action!');
                    return;
                }
                let allchildren = parent.getDescendants();
                let nofc = 0;
                for (var ch of allchildren) {
                    if (ch.type == 'behaviour_chained_action') {
                        nofc = nofc + 1;
                    }
                    if (nofc >= 2 && parent.getFieldValue('SCRIPTS') != 'choice_selection') {
                        alert('Only ONE chained actionlet can be attached directly to an action. UNDO your last action!');
                        return;
                    }
                }
            }
            else if (block.type == 'behaviour_action') {
                if (!event.newParentId) {
                    return;
                }
                let parent = block.getSurroundParent();
                if (!parent) return;
                if (!(parent.type == "behaviour_behaviour" || (parent.type.startsWith('controls') && parent.type != 'controls_if'))) {
                    alert('Action can only be attached directly to behaviour or loops. UNDO your last action!');
                    return;
                }
            }
            else if (block.type.endsWith('primitive')) {
                if (!event.newParentId) {
                    return;
                }
                let parent = block.getSurroundParent();
                if (!parent) return;
                if (!(parent.type.endsWith("action") || parent.type.endsWith('primitive') || parent.type == "key_action_store" || parent.type == "controls_if")) {
                    alert('Actionlet can only be attached directly to action or other primitive block. UNDO your last action!');
                    return;
                }
            }
            else if (block.type.startsWith('controls')) {
                if (!event.newParentId) {
                    return;
                }
                let parent = block.getSurroundParent();
                if (!parent) return;
                if (parent.type != "behaviour_behaviour") {
                    alert('Control loop can only be attached directly to a behaviour block. UNDO your last action!');
                    return;
                }
            }
            else if (block.type == 'variables_set' || block.type == 'math_change') {
                if (!event.newParentId) {
                    return;
                }
                let parent = block.getSurroundParent();
                if (!parent) return;
                if (!(parent.type == "behaviour_action" || parent.type.endsWith('primitive'))) {
                    alert('Set variable number can only be attached directly to an action block or a primitive. UNDO your last action!');
                    return;
                }
            }
        }
        else if (event.type == Blockly.Events.BLOCK_DELETE) {
            for (var dId of event.ids) {
                let found = -1;
                // update play action let cache first
                let all = Code.existingPlayBehaviorActionLets.length;
                for (let i = 0; i < all; i++) {
                    if (Code.existingPlayBehaviorActionLets[i].id == dId) {
                        found = i;
                        break;
                    }
                }
                if (found != -1) {
                    Code.existingPlayBehaviorActionLets.splice(found,1);
                }
            }

            let be_names = Object.keys(Code.existingBehaviours);
            for (var dId of event.ids) {
                let found = null;
                for (var be of be_names) {
                    if (Code.existingBehaviours[be].id === dId) {
                        found = be;
                        break;
                    }
                }
                if (found) {
                    delete Code.existingBehaviours[found];
                    be_names = Object.keys(Code.existingBehaviours);
                    for (var pba of Code.existingPlayBehaviorActionLets) {
                        let fvalue = [['','']];
                        for (var v of be_names) {
                            fvalue.push([v, v]);
                        }
                        let newbel = new Blockly.FieldDropdown(fvalue);
                        let fin = pba.getInput('SELECT_BEHAVIOUR');
                        let selected_be = pba.getFieldValue('BEHAVIOURS');
                        if (selected_be == found) { // we have selected the deleted behaviour
                            if (be_names.length > 0) {
                                selected_be = be_names[0];
                            }
                            else {
                                selected_be = '';
                            }
                        }
                        newbel.setValue(selected_be);
                        fin.removeField('BEHAVIOURS');
                        fin.insertFieldAt(1, newbel, 'BEHAVIOURS');
                    }
                }
            }
        }
    },
    /**
     * Switch the visible pane when a tab is clicked.
     * @param {string} clickedName Name of tab clicked.
     */
    tabClick: function(clickedName) {
        if (document.getElementById('tab_blocks').className == 'tabon') {
            Code.workspace.setVisible(false);
        }
        // Deselect all tabs and hide all panes.
        for (let i = 0; i < Code.TABS_.length; i++) {
            var name = Code.TABS_[i];
            document.getElementById('tab_' + name).className = 'taboff';
            document.getElementById('content_' + name).style.visibility = 'hidden';
        }

        // Select the active tab.
        Code.selected = clickedName;
        document.getElementById('tab_' + clickedName).className = 'tabon';
        // Show the selected pane.
        document.getElementById('content_' + clickedName).style.visibility =
          'visible';
        Code.renderContent();
        if (clickedName == 'blocks') {
            Code.workspace.setVisible(true);
        }
        Blockly.svgResize(Code.workspace);
    },
    /**
     * Populate the currently selected pane with content generated from the blocks.
     */
    renderContent: function() {
        let content = document.getElementById('content_' + Code.selected);
        // Initialize the pane.
        if (content.id == 'content_lurawi') {
            Code.saveFile.setAttribute('title', 'Save generated lurawi code to a local JSON file.');
            Code.attemptCodeGeneration(Blockly.LurawiKit, 'json');
        }
        else {
            Code.saveFile.setAttribute('title', 'Save blocks to a local XML file.');
        }
    },
    /**
     * Attempt to generate the code and display it in the UI, pretty printed.
     * @param generator {!Blockly.Generator} The generator to use.
     * @param prettyPrintType {string} The file type key for the pretty printer.
     */
    attemptCodeGeneration: function(generator, prettyPrintType) {
        let content = document.getElementById('content_' + Code.selected);
        let code = generator.workspaceToCode(Code.workspace);
        let jsoncode = null;
        if (code) {
            try {
                jsoncode = JSON.parse(code);
            }
            catch(error) {
                content.textContent = "Invalid code. " + error;
                if (!content.hasAttribute("readonly")) {
                    content.setAttribute("readonly", '');
                    content.setAttribute("disabled", '');
                }
                console.log("error generating json code");
                console.log(code)
                return;
            }
            if (content.hasAttribute("readonly")) {
                content.removeAttribute("readonly");
                content.removeAttribute("disabled");
            }
            content.textContent = JSON.stringify(jsoncode, null, 2);
        }
        else {
            if (!content.hasAttribute("readonly")) {
                content.setAttribute("readonly", '')
                content.setAttribute("disabled", '');
            }
            content.textContent = "Build your code from the block tab";
        }
    },
    /**
     * Check whether all blocks in use have generator functions.
     * @param generator {!Blockly.Generator} The generator to use.
     */
    checkAllGeneratorFunctionsDefined: function(generator) {
        var blocks = Code.workspace.getAllBlocks();
        var missingBlockGenerators = [];
        for (var i = 0; i < blocks.length; i++) {
            var blockType = blocks[i].type;
            if (!generator[blockType]) {
                if (missingBlockGenerators.indexOf(blockType) === -1) {
                    missingBlockGenerators.push(blockType);
                }
            }
        }

        var valid = missingBlockGenerators.length == 0;
        if (!valid) {
            var msg = 'The generator code for the following blocks not specified for '
                + generator.name_ + ':\n - ' + missingBlockGenerators.join('\n - ');
            Blockly.alert(msg);  // Assuming synchronous. No callback.
        }
        return valid;
    },
    /**
     * Discard all blocks from the workspace.
     */
    discard: function() {
        let count = Code.workspace.getAllBlocks().length;
        if (count < 2 || window.confirm(Blockly.Msg['DELETE_ALL_BLOCKS'].replace('%1', count))) {
            Code.workspace.clear();
            if (window.location.hash) {
                window.location.hash = '';
            }
        }
    },
    /**
     * Initialize Blockly.  Called on page load.
     */
    init: function() {
        Code.selected = 'blocks';

        Code.container = document.getElementById('content_area');

        Code.inCodeExecution = false;

        var toolbox = document.getElementById('toolbox');
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
            Code.customScripts[cname] = cargs;
        }
        // The toolbox XML specifies each category name using Blockly's messaging
        // format (eg. `<category name="%{BKY_CATLOGIC}">`).
        // These message keys need to be defined in `Blockly.Msg` in order to
        // be decoded by the library. Therefore, we'll use the `MSG` dictionary that's
        // been defined for each language to import each category name message
        // into `Blockly.Msg`.
        // TODO: Clean up the message files so this is done explicitly instead of
        // through this for-loop.
        /*
        for (var messageKey in MSG) {
        if (messageKey.indexOf('cat') == 0) {
          Blockly.Msg[messageKey.toUpperCase()] = MSG[messageKey];
        }
        }

        // Construct the toolbox XML, replacing translated variable names.
        var toolboxText = document.getElementById('toolbox').outerHTML;
        toolboxText = toolboxText.replace(/(^|[^%]){(\w+)}/g,
          function(m, p1, p2) {return p1 + MSG[p2];});
        var toolboxXml = Blockly.Xml.textToDom(toolboxText);
        */
        Code.options['toolbox'] = toolbox;
        Code.workspace = Blockly.inject('content_blocks', Code.options);
        
        Code.loadFile = document.getElementById('file-input');
        Code.saveFile = document.getElementById('file-output');
        Code.sendFile = document.getElementById('file-send');
        Code.testConsole = document.getElementById('test-console');
        Code.documentation = document.getElementById('lurawi-doc');
        //Code.sendFile.setAttribute('hidden', '');
        Code.tabClick(Code.selected);

        for (var i = 0; i < Code.TABS_.length; i++) {
            var name = Code.TABS_[i];
            Code.bindClick('tab_' + name,
                function(name_) {return function() {Code.tabClick(name_);};}(name));
        }
        window.addEventListener('resize', Code.onresize, false);
        Code.workspace.addChangeListener(Code.blockEvent);
        Code.loadFile.addEventListener('input', Code.handleLoadFile, false);
        Code.saveFile.addEventListener('click', Code.handleSaveFile, false);
        Code.sendFile.addEventListener('click', Code.handleSendFile, false);
        Code.testConsole.addEventListener('click', Code.openTestConsole, false);
        Code.documentation.addEventListener('click', Code.openDocumatation, false);
        Code.onresize();
        Blockly.svgResize(Code.workspace);

    },
    bindClick: function(el, func) {
      if (typeof el == 'string') {
        el = document.getElementById(el);
      }
      el.addEventListener('click', func, true);
      el.addEventListener('touchend', func, true);
    }
};
window.addEventListener('load', Code.init);
