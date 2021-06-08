import xml.etree.ElementTree as ET
import json
from pathlib import Path

logic_file = "Confidentiality_agreement.lgc"
cmp_filename = Path(logic_file).stem + '.cmp'

tree = ET.parse(logic_file)
lgc_root = tree.getroot()

namespace = 'http://www.hotdocs.com/schemas/component_library/2009'
ET.register_namespace('hd', namespace)

cmp_root = ET.Element('{'+namespace+'}componentLibrary')
cmp_root.set('version','12')

cmp_preferences = ET.SubElement(cmp_root, '{'+namespace+'}preferences')

# make this configurable
prefs = {'MAX_REPEAT_COUNT':'100', 'MAX_STACK_DEPTH':'100'}
for key in prefs.keys():
    preference = ET.SubElement(cmp_preferences, '{'+namespace+'}preference')
    preference.set('name', key)
    preference.text = prefs[key]

variables = {}
variables["MultipleChoiceQuestion"] = {}
variables["UserTextQuestion"] = {}
variables["Calculation"] = {}
variables["DynamicMultipleChoiceQuestion"] = {}
variables["Condition"] = {}

# fetch all logic variable elems
cmp_components = ET.SubElement(cmp_root, '{'+namespace+'}components')

logic_variables = lgc_root.findall("./LogicSetup/Variables/")
for logic_variable in logic_variables:
    #child.attrib
    query_id = logic_variable.get('query')
    query_name = logic_variable.get('name')
    query_details = lgc_root.find("./LogicSetup/Queries/Query[@name='" + query_id + "']")

    # calculation repeats requires dataytype
    query_type = logic_variable.get('type')

    # fetch non boolean variables
    if logic_variable.tag == "Variable":
        # if variable has repeater, repeater elem becomes the second child elem
        # else the second child element determines the variable type
        # @note repeater is used differently in HotDocs
        if query_details[1].tag == "Repeater":
            data = query_details[2]
        else:
            data = query_details[1]

        variable_type = data.tag

        #@todo extract and parse guidance notes
        if variable_type == "MultipleChoiceQuestion":
            layout = data.get("Layout") or ""
            priority = data.get("Priority") or ""
            topic = data.find("Topic").text
            question = data.find("Question").text

            #@todo differentiate multi select vs single select
            cmp_mcq = ET.SubElement(cmp_components, '{'+namespace+'}multipleChoice')
            cmp_mcq.set('name', query_name + '_SelectionVariable')
            mcq_title = ET.SubElement(cmp_mcq, '{'+namespace+'}title')
            mcq_title.text = topic
            mcq_prompt = ET.SubElement(cmp_mcq, '{'+namespace+'}prompt')
            mcq_prompt.text = question
            mcq_options = ET.SubElement(cmp_mcq, '{'+namespace+'}options')
            mcq_option = ET.SubElement(mcq_options, '{'+namespace+'}option')
            mcq_option.set('name', 'BUILTIN_AnswerSource')
            mcq_option_prompt = ET.SubElement(mcq_option, '{'+namespace+'}prompt')
            mcq_option_prompt.text = 'Value_DisplayColumn'

            # mcq elem is always followed by options table elem
            cmp_mcq_option_table = ET.SubElement(cmp_components, '{'+namespace+'}computation')
            cmp_mcq_option_table.set('name', query_name + '.BUILTIN_OptionTable')
            
            cmp_mcq_option_table_script = ET.SubElement(cmp_mcq_option_table, '{'+namespace+'}script')
            cmp_mcq_option_table_fields = {}
            cmp_mcq_option_table_fields['Fields'] = [{"IsKey":True,"Name":"Key","Type":1}, {"Name":"Value","Type":1}]

            # designate mcq option table as key/val pairs
            cmp_mcq_option_table_fields['Rows'] = []

            responses = data.find("Responses")
            for response in responses:
                # prompts in some variables in NewWAM were wrapped with <p>
                if response.find("Prompt/p") is not None:
                    prompt = response.find("Prompt/p").text
                else:
                    prompt = response.find("Prompt").text
                
                value = response.find("SetValueTo").text
                cmp_mcq_option_table_fields['Rows'].append([value,prompt])            
            
            # HotDocs requires a newline char after the QUIT keywork on option table
            cmp_mcq_option_table_script.text = 'QUIT\n'+ json.dumps(cmp_mcq_option_table_fields)

        elif variable_type == "UserTextQuestion":
            layout = data.get("Layout") or ""
            priority = data.get("Priority") or ""
            rows = data.get("Rows") or ""
            columns = data.get("Columns") or ""
            topic = data.find("Topic").text
            question = data.find("Question").text

            cmp_utq = ET.SubElement(cmp_components, '{'+namespace+'}text')
            cmp_utq.set('name', query_name)
            cmp_utq_title = ET.SubElement(cmp_utq, '{'+namespace+'}title')
            cmp_utq_title.text = topic
            
            # HotDocs does not have equivalent example text structure
            example_text = ""
            if data.find("ExampleText") is not None:
                example_text = data.find("ExampleText").text

            default_text_data = ""
            if data.find("DefaultText") is not None:
                cmp_utq_defMergeProps = ET.SubElement(cmp_utq, '{'+namespace+'}defMergeProps')

                default_text = data.find("DefaultText")
                # parsing of XML nodes is unpredictable so do not process default text that contains mixed text node and sub elems
                # only process text OR single InsertVariable sub elem
                # we do not process ConditionalPhrase due to the same mixed text node and InsertVariable issue
                # report those UserTextQuestion that contains ConditionalPhrase or multiple sub elems
                sub_elem_count = len(list(default_text))
                if default_text.text is not None and sub_elem_count == 0:
                    default_text_data = default_text.text
                    cmp_utq_defMergeProps.set('unansweredText', default_text_data)
                elif default_text.text is None and sub_elem_count > 0:
                    if(default_text.find("ConditionalPhrase")) is not None:
                        print("Unsupported default text sub element")
                    else:
                        default_text_data = "IDREF:" + default_text.find("InsertVariable").get("IDREF")
                        cmp_utq_defMergeProps.set('unansweredText', default_text_data)
                else:
                    print("Unsupported default text structure at " + query_id)

            cmp_utq_prompt = ET.SubElement(cmp_utq, '{'+namespace+'}prompt')
            cmp_utq_prompt.text = question
            cmp_utq_fieldWidth = ET.SubElement(cmp_utq, '{'+namespace+'}fieldWidth')
            cmp_utq_fieldWidth.set('widthType', 'calculated')
        
        elif variable_type == "SmartPhrase":
            cmp_sp = ET.SubElement(cmp_components, '{'+namespace+'}computation')
            cmp_sp.set('name', query_name)
            cmp_sp.set('resultType', 'text')
            cmp_sp_script = ET.SubElement(cmp_sp, '{'+namespace+'}script')

            # can only process simple smartphrases
            smartphrase_list = ''
            for sub_elem in data.iter():
                if sub_elem.tag == "SmartPhrase":
                    # do not process the root elem
                    pass
                elif sub_elem.tag == "ConditionalPhrase":
                    #smartphrase_condition = sub_elem.get('Condition').split('.')
                    #print(sub_elem.get('Condition'), sub_elem.text)
                    smartphrase_list = smartphrase_list + sub_elem.get('Condition') + ':' + sub_elem.text + ';'
                    #smartphrase_list.append({smartphrase_condition[1]:sub_elem.text})

                else:
                    print("Unable to porcess conditional phrase at " + query_id)

            smartphrase_list = smartphrase_list.split(';')
            smartphrase_condition = smartphrase_list[0].split(':')
            smartphrase_condition_list = smartphrase_condition[0].split('.')
            script_string = 'IF ' + smartphrase_condition_list[0] +' CONTAINS ' + '\"' + smartphrase_condition_list[1] + '\"\n'
            script_string = script_string + 'RESULT \"' + smartphrase_condition[1] + '\"\n'

            i = 1
            while i < len(smartphrase_list):
                if smartphrase_list[i] != '':
                    smartphrase_condition = smartphrase_list[i].split(':')
                    smartphrase_condition_list = smartphrase_condition[0].split('.')
                    script_string = script_string + 'ELSE IF ' + smartphrase_condition_list[0] +' CONTAINS \"' + smartphrase_condition_list[1] + '\"\n'
                    script_string = script_string + 'RESULT \"' + smartphrase_condition[1] + '\"\n'
                i = i + 1

            script_string = script_string + 'END IF'
            cmp_sp_script.text = script_string

        elif variable_type == "Calculation":
            # calculation in HotDocs does not use JS and uses a different paradigm
            pass_repeat_index = data.get("PassRepeatIndex") or ""

            #@todo strip whitespaces
            script = data.find("script").text or ""
            explanatory_blurb = data.find("ExplanatoryBlurb") or ""
            parameters = data.find("Parameters")
            variables[variable_type][query_id] = {}
            variables[variable_type][query_id].update({
                "Name":query_name,
                "DataType":query_type,
                "PassRepeatIndex":pass_repeat_index,
                "script":script,
                "ExplanatoryBlurb":explanatory_blurb})
            variables[variable_type][query_id]["Parameters"] = {}

            for parameter in parameters:
                parameter_name = parameter.get("name") or ""
                parameter_ref = parameter.get("ref") or ""

                # items to be added should be key:val pair else only the last
                # in the list will be added
                variables[variable_type][query_id]["Parameters"].update({parameter_name:parameter_ref})
            
            # create whitespace stripped values from UTQ
            if query_name.lower().find("trim") != -1:
                cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                cmp_computation.set('name', query_name)
                cmp_computation.set('resultType', 'text')
                cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                cmp_computation_script.text = "TRIM(" + query_name + ")"

        elif variable_type == "DynamicMultipleChoiceQuestion":
            # DMCQ derives source mostly from CALC
            layout = data.get("Layout") or ""
            priority = data.get("Priority") or ""
            topic = data.find("Topic").text
            question = data.find("Question").text
            response_source = data.find("ResponseSource").get("ref")
            device = data.get("Device") or ""
            multiple_select_toggle = data.get("MultipleSelectToggle") or ""

            variables[variable_type][query_id] = {}
            variables[variable_type][query_id].update({
                "Name":query_name,
                "DataType":query_type,
                "Layout":layout,
                "Priority":priority,
                "Topic":topic,
                "Question":question,
                "Device":device,
                "MultipleSelectToggle":multiple_select_toggle,
                "ResponseSource":response_source})
        else:
            print("Unsupported variable at " + query_id)
    elif logic_variable.tag == "Condition":
        # Condition in Hotdocs are calculations that have boolean return value
        data = query_details[1]
        variable_type = data.tag

        if variable_type == "Calculation":
            pass_repeat_index = data.get("PassRepeatIndex") or ""

            #@todo strip whitespaces
            script = data.find("script").text or ""
            parameters = data.find("Parameters")
            variables["Condition"][query_id] = {}
            variables["Condition"][query_id].update({
                "Name":query_name,
                "PassRepeatIndex":pass_repeat_index,
                "script":script})
            variables["Condition"][query_id]["Parameters"] = {}

            for parameter in parameters:
                parameter_name = parameter.get("name") or ""
                parameter_ref = parameter.get("ref") or ""

                # items to be added should be key:val pair else only the last
                # in the list will be added
                variables["Condition"][query_id]["Parameters"].update({parameter_name:parameter_ref})
        elif variable_type == "ConditionExpression":

            # short circuit, just create Hotdocs calculation variable for _Known.Yes condition
            if query_name.lower().find('known') != -1:
                if query_name.lower().find('yes') != -1:
                    # Hotdocs does not allow period on variable names
                    variable_name = query_name.replace('.', '')
                    variable_name = variable_name[0:variable_name.lower().find('known') -1 ]

                    cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                    cmp_computation.set('name', variable_name + '_Known_Yes')
                    cmp_computation.set('resultType', 'trueFalse')
                    cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                    cmp_computation_script.text = "ANSWERED("+variable_name+") AND TRIM("+variable_name+") != ''"

            # deal with multiple conditions, negation condition, or simple variable value test
            stack1 = []
            stack2 = []

            for sub_elem in data.iter():
                if sub_elem.tag == "ConditionExpression":
                    # do not add the root elem
                    pass
                elif sub_elem.tag == "Test":
                    # add extra mark to distinguish between variable
                    # value test vs condition test
                    elem_attrib = sub_elem.attrib.update({"Tag":sub_elem.tag})
                    stack1.append(sub_elem.attrib)
                    #@todo should we pop the second stack for negation condition?

                elif sub_elem.tag == "UseCondition":
                    elem_attrib = sub_elem.attrib.update({"Tag":sub_elem.tag})
                    stack1.append(sub_elem.attrib)
                else:
                    # add condition operators using postfix notation
                    stack1.append(sub_elem.tag)

            # create infix notation using postfix stack structure
            condition_expr = ""
            while len(stack1) > 0:
                operator = stack1.pop()
                if isinstance(operator, dict):
                    if operator["Tag"] == "UseCondition":
                        stack2.append(operator["IDREF"])
                    elif operator.get("Tag") == "Test":
                        if operator.get("Value") is not None:
                            condition_expr = operator["IDREF"] + " == " + operator["Value"]
                        else:
                            condition_expr = operator["IDREF"] + " == ''"

                        stack2.append(condition_expr)
                    else:
                        print("Unsupported condition expression structure at " + query_id)
                else:
                    if operator == "Not":
                        # negation operator always uses prefix notation
                        try:
                            operand1 = stack2.pop()
                        except ValueError:
                            print("Error processing condition " + query_id)
                        
                        condition_expr = "(" + operator + " " + operand1 + ")"
                        stack2.append(condition_expr)
                    else:
                        try:
                            operand1 = stack2.pop()
                        except ValueError:
                            print("Error processing condition " + query_id)

                        try:
                            operand2 = stack2.pop()
                        except ValueError:
                            print("Error processing condition " + query_id)

                        condition_expr = "(" + operand1 + " " + operator + " " + operand2 + ")"
                        stack2.append(condition_expr)

            variables["Condition"][query_id] = {}
            try:
                final_condition = stack2.pop()
                variables["Condition"][query_id].update({"Name":query_name,"Condition":final_condition})
            except ValueError:
                print("Error processing condition " + query_id)

    elif logic_variable.tag == "Repeat":
        # repeats in Hotdocs are just bundled variables in a Dialog variable and returns a List Record
        data = query_details[1]
        variable_type = data.tag

        # normal repeats are just special UTQs
        if variable_type == "UserTextQuestion":
            layout = data.get("Layout") or ""
            priority = data.get("Priority") or ""
            rows = data.get("Rows") or ""
            columns = data.get("Columns") or ""
            topic = data.find("Topic").text
            question = data.find("Question").text

            example_text = ""
            if data.find("ExampleText") is not None:
                example_text = data.find("ExampleText").text
            
            # we do not process complicated default text
            default_text_data = ""
            if data.find("DefaultText") is not None:
                default_text_data = data.find("DefaultText").text

                variables[variable_type][query_id] = {}
                variables[variable_type][query_id].update({
                    "Name":query_name,
                    "DataType":query_type,
                    "Layout":layout,
                    "Priority":priority,
                    "Topic":topic,
                    "Question":question,
                    "Rows":rows,
                    "Columns":columns,
                    "ExampleText":example_text,
                    "DefaultText":default_text_data})
        elif variable_type == "Calculation":
            pass_repeat_index = data.get("PassRepeatIndex") or ""

            #@todo strip whitespaces
            script = data.find("script").text or ""
            explanatory_blurb = data.find("ExplanatoryBlurb") or ""
            parameters = data.find("Parameters")
            variables[variable_type][query_id] = {}
            variables[variable_type][query_id].update({
                "Name":query_name,
                "DataType":query_type,
                "PassRepeatIndex":pass_repeat_index,
                "script":script,
                "ExplanatoryBlurb":explanatory_blurb})
            variables[variable_type][query_id]["Parameters"] = {}

            for parameter in parameters:
                parameter_name = parameter.get("name") or ""
                parameter_ref = parameter.get("ref") or ""

                # items to be added should be key:val pair else only the last
                # in the list will be added
                variables[variable_type][query_id]["Parameters"].update({parameter_name:parameter_ref})            

with open('data.json', 'w') as f:
    json.dump(variables, f, indent=4)

# create a new XML file with the results
tree = ET.ElementTree(cmp_root)

#@see https://stackoverflow.com/questions/15356641/how-to-write-xml-declaration-using-xml-etree-elementtree
tree.write(cmp_filename, encoding='utf-8', xml_declaration=True, method = 'xml')