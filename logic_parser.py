#!/usr/bin/env python
from pathlib import Path
import argparse
import xml.etree.ElementTree as ET
import json

def convert_logic_file( logic_file ):
    tree = ET.parse(logic_file)
    lgc_root = tree.getroot()

    # @todo make this configurable in an external file
    namespace = 'http://www.hotdocs.com/schemas/component_library/2009'
    ET.register_namespace('hd', namespace)

    cmp_root = ET.Element('{'+namespace+'}componentLibrary')
    cmp_root.set('version','12')

    cmp_preferences = ET.SubElement(cmp_root, '{'+namespace+'}preferences')

    # @todo make this configurable in an external file
    prefs = {'MAX_REPEAT_COUNT':'100', 'MAX_STACK_DEPTH':'100'}
    for key in prefs.keys():
        preference = ET.SubElement(cmp_preferences, '{'+namespace+'}preference')
        preference.set('name', key)
        preference.text = prefs[key]

    variables = {}
    variables["Stats"] = {"total": 0, "ignored": 0, "error": 0, "unknown": 0}
    variables["MultipleChoiceQuestion"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["UserTextQuestion"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["Calculation"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["DynamicMultipleChoiceQuestion"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["ConditionExpression"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["SmartPhrase"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["Repeat"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["IncrementingRepeat"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["IncrementingRepeat"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["Constant"] = {"stats": {"total": 0, "ignored":0, "error": 0}}
    variables["Data"] = {}

    cmp_components = ET.SubElement(cmp_root, '{'+namespace+'}components')

    # fetch all logic variable elems
    logic_variables = lgc_root.findall("./LogicSetup/Variables/")
    error_msg = ""
    cond_search_str = {}

    for logic_variable in logic_variables:
        query_id = logic_variable.get('query')
        query_name = logic_variable.get('name')
        query_details = lgc_root.find("./LogicSetup/Queries/Query[@name='" + query_id + "']")
        query_type = logic_variable.get('type')

        variables["Stats"]["total"] = int(variables["Stats"]["total"]) + 1

        # fetch non boolean variables
        if logic_variable.tag == "Variable":
            # if variable has repeater, repeater elem becomes the second child elem
            # else the second child element determines the variable type
            # @note in HotDocs, repeater can only be used in a Dialog and can be used as basis for grouping
            if (query_details[1].tag == "Repeater") or (query_details[1].tag == "Comment"):
                data = query_details[2]
            else:
                data = query_details[1]

            variable_type = data.tag

            if data.find("Topic") is not None:
                topic = data.find("Topic").text
                topic = topic.strip()
                if not (topic in variables["Data"]):
                    variables["Data"][topic] = {}

            # @note there is no such thing as questionnaire specific guidance notes in HotDocs
            if variable_type == "MultipleChoiceQuestion":
                question = data.find("Question").text
                cardinality = data.get("Cardinality") or "Single"

                cmp_mcq = ET.SubElement(cmp_components, '{'+namespace+'}multipleChoice')
                cmp_mcq.set('name', query_name + '_SelectionVariable')

                # @warn warnIfUnanswered flag causes the CMP to fail on component studio
                #if (cardinality == 'MultipleOrNone'):
                #    cmp_mcq.set('warnIfUnanswered', 'False')

                cmp_mcq_prompt = ET.SubElement(cmp_mcq, '{'+namespace+'}prompt')
                cmp_mcq_prompt.text = question

                cmp_mcq_options = ET.SubElement(cmp_mcq, '{'+namespace+'}options')
                cmp_mcq_option = ET.SubElement(cmp_mcq_options, '{'+namespace+'}option')
                cmp_mcq_option.set('name', 'BUILTIN_AnswerSource')
                cmp_mcq_option_prompt = ET.SubElement(cmp_mcq_option, '{'+namespace+'}prompt')
                cmp_mcq_option_prompt.text = 'Prompt_DisplayColumn'

                if (cardinality == 'MultipleOrNone') or (cardinality == 'Multiple'):
                    cmp_mcq_multiple_selection = ET.SubElement(cmp_mcq, '{'+namespace+'}multipleSelection')

                # mcq elem is always followed by its options table elem
                cmp_mcq_option_table = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                cmp_mcq_option_table.set('name', query_name + '.BUILTIN_OptionTable')
                
                cmp_mcq_option_table_script = ET.SubElement(cmp_mcq_option_table, '{'+namespace+'}script')
                cmp_mcq_option_table_fields = {}
                cmp_mcq_option_table_fields['Fields'] = [{"IsKey":True,"Name":"Key","Type":1}, {"Name":"Prompt","Type":1}]

                # designate mcq option table as key/val pairs
                cmp_mcq_option_table_fields['Rows'] = []

                responses = data.find("Responses")
                for response in responses:
                    # prompts in some variables in WAM were wrapped with <p>
                    if response.find("Prompt/p") is not None:
                        prompt = response.find("Prompt/p").text
                    else:
                        prompt = response.find("Prompt").text
                    if response.find("SetValueTo") is not None:
                        value = response.find("SetValueTo").text
                    else:
                        value = ""
                    cmp_mcq_option_table_fields['Rows'].append([value,prompt])
                
                # HotDocs requires a newline char after the QUIT keywork on option table
                cmp_mcq_option_table_script.text = 'QUIT\n'+ json.dumps(cmp_mcq_option_table_fields)

                # arrange MCQs based on topic
                if (data.get("Priority") is None) or (data.get("Priority") == ""):
                    priority = 0
                else:
                    priority = float(data.get("Priority"))

                topic = topic.strip()
                variables["Data"][topic][query_id] = {"Name":query_name, "Priority":priority}
                variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

            elif variable_type == "UserTextQuestion":
                rows = data.get("Rows") or "1"
                columns = data.get("Columns") or "20"
                question = data.find("Question").text

                # all UTQ specific variables should not have periods on variables names
                # periods will be replaced with underscore and should be specific to conditions as much as possible
                variable_name = query_name
                variable_name = variable_name.replace('.', '')
                # @note Hotdocs has maximum lenght of 100 for variable name
                # @note we no longer trim variables names since there is a possibillity that there are trimmed
                # variable names that have the same name
                if len(variable_name) > 99:
                    error_msg = error_msg + "Maximum variable name length on " + query_name + "\n"
                    variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                else:
                    # check if there is already a variable with the same name
                    if variable_name in cond_search_str:
                        error_msg = error_msg + variable_name + " already exists, see " + query_id + "\n"
                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                    else:
                        if (query_type == "Date-DDMonthYYYY-AllowBlank") or (query_type == "Date-DDMMYYYY-AllowBlank"):
                            # date datatypes
                            cmp_utq = ET.SubElement(cmp_components, '{'+namespace+'}date')
                            cmp_utq.set('name', variable_name)

                            cmp_utq_format = ET.SubElement(cmp_utq, '{'+namespace+'}defFormat')
                            # @todo make this configurable
                            cmp_utq_format.text = "d Mmmm yyyy"
                            cmp_utq_prompt = ET.SubElement(cmp_utq, '{'+namespace+'}prompt')
                            cmp_utq_prompt.text = question
                            cmp_utq_field_width = ET.SubElement(cmp_utq, '{'+namespace+'}fieldWidth')
                            cmp_utq_field_width.set('widthType', 'exact')
                            cmp_utq_field_width.set('exactWidth', columns)

                            variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

                        elif (query_type == "integer") or (query_type == "positiveInteger") or \
                            (query_type == "nonNegativeInteger") or (query_type == "Number-3d-3d-3d.00-AllowBlank") or \
                            (query_type == "NonNegativeIntegerOrNothing") or (query_type == "decimal") or \
                            (query_type == "Number-CurrencyValue-GBP") or (query_type == "Number-Percentage-AllowBlank"):
                            # integer data types
                            cmp_utq = ET.SubElement(cmp_components, '{'+namespace+'}number')
                            cmp_utq.set('name', variable_name)

                            if query_type == "Number-3d-3d-3d.00-AllowBlank":
                                cmp_utq.set('decimalPlaces', '2')

                            cmp_utq_format = ET.SubElement(cmp_utq, '{'+namespace+'}defFormat')
                            # @todo make this configurable
                            cmp_utq_format.text = "9,999.00"
                            cmp_utq_prompt = ET.SubElement(cmp_utq, '{'+namespace+'}prompt')
                            cmp_utq_prompt.text = question
                            cmp_utq_field_width = ET.SubElement(cmp_utq, '{'+namespace+'}fieldWidth')
                            cmp_utq_field_width.set('widthType', 'exact')
                            cmp_utq_field_width.set('exactWidth', columns)

                            variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

                        elif (query_type == "string") or (query_type == "NonEmptyString"):
                            # string datatypes
                            cmp_utq = ET.SubElement(cmp_components, '{'+namespace+'}text')
                            cmp_utq.set('name', variable_name)

                            cmp_utq_prompt = ET.SubElement(cmp_utq, '{'+namespace+'}prompt')
                            cmp_utq_prompt.text = question
                            cmp_utq_field_width = ET.SubElement(cmp_utq, '{'+namespace+'}fieldWidth')
                            cmp_utq_field_width.set('widthType', 'exact')
                            cmp_utq_field_width.set('exactWidth', columns)

                            if int(rows) > 1:
                                cmp_utq_multi_line = ET.SubElement(cmp_utq, '{'+namespace+'}multiLine')
                                cmp_utq_multi_line.set('height', rows)

                            variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

                        else:
                            # @note repeats are also UTQs with NonNegativeIntegerOrNothing datatype
                            variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1
                            error_msg = error_msg + "Unsupported UserTextQuestion datatype at " + query_id + "\n"

                        # arrange UTQs based on topic
                        if (data.get("Priority") is None) or (data.get("Priority") == ""):
                            priority = 0
                        else:
                            priority = float(data.get("Priority"))

                        topic = topic.strip()
                        variables["Data"][topic][query_id] = {"Name":query_name, "Priority":priority}

                        # add the variable name into search string
                        cond_search_str[variable_name] = variable_name

            elif variable_type == "SmartPhrase":
                    variable_name = query_name
                    variable_name = variable_name.replace('.', '')
                    # @note Hotdocs has maximum lenght of 100 for variable name
                    if len(variable_name) > 99:
                        error_msg = error_msg + "Maximum variable name length on " + query_name + "\n"
                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                    else:
                        # check if there is already a variable with the same name
                        if variable_name in cond_search_str:
                            error_msg = error_msg + variable_name + " already exists, see " + query_id + "\n"
                            variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                        else:
                            # can only process well-formed simple smartphrases
                            smartphrase_conditions = []
                            for sub_elem in data.iter():
                                if sub_elem.tag == "SmartPhrase":
                                    # do not process the root elem
                                    pass
                                elif sub_elem.tag == "ConditionalPhrase":
                                    smartphrase_conditions.append(sub_elem)
                                else:
                                    # InsertVariable elems in Exari does not have any equivalent structure
                                    # in Hotdocs so we disregard the SmartPhrase
                                    smartphrase_conditions = []
                                    break
                            if len(smartphrase_conditions) > 0:
                                ctr = 1
                                script_string = ""
                                while len(smartphrase_conditions) > 0:
                                    smartphrase_condition = smartphrase_conditions.pop()
                                    if isinstance(smartphrase_condition, ET.Element):
                                        # replace period on conditions
                                        if smartphrase_condition.get('Condition') is not None:
                                            variable = smartphrase_condition.get('Condition').replace('.', '_')
                                            if ctr == 1:
                                                script_string = "IF " + variable
                                            else:
                                                script_string = script_string + "ELSE IF " + variable

                                            if smartphrase_condition.text is not None:
                                                script_string = script_string + " RESULT " + "\"" + smartphrase_condition.text.strip() + "\"\n"
                                            else:
                                                script_string = script_string + "\n"
                                        else:
                                            variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                            error_msg = error_msg + "Invalid SmartPhrase declaration at " + query_id + "\n"
                                    else:
                                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                        error_msg = error_msg + "Unexpected element on SmartPhrase at " + query_id + "\n"

                                    ctr = ctr + 1

                                cmp_sp = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                                cmp_sp.set('name', variable_name)
                                cmp_sp.set('resultType', 'text')
                                cmp_sp_script = ET.SubElement(cmp_sp, '{'+namespace+'}script')

                                script_string = script_string + "END IF"
                                cmp_sp_script.text = script_string

                                variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1
                            else:
                                error_msg = error_msg + "Unsupported SmartPhrase structure at " + query_id + "\n"
                                variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1

                            # add the variable name into search string
                            cond_search_str[variable_name] = variable_name

            elif variable_type == "Calculation":
                # @note calculation in HotDocs does not use JS
                # @note repetition is done using Dialog variables
                variable_name = query_name
                variable_name = variable_name.replace('.', '_')

                # @note Hotdocs has maximum lenght of 100 for variable name
                if len(variable_name) > 99:
                    error_msg = error_msg + "Maximum variable name length on " + query_name + "\n"
                    variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                else:
                    # check if there is already a variable with the same name
                    if variable_name in cond_search_str:
                        error_msg = error_msg + variable_name + " already exists, see " + query_id + "\n"
                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                    else:
                        if query_type == 'integer':
                            variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1
                            error_msg = error_msg + "Unsupported Calculation with return type integer at " + query_id + "\n"

                            # create placeholder variable
                            cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                            cmp_computation.set('name', variable_name)
                            cmp_computation.set('resultType', 'number')
                            cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                            cmp_computation_script.text = "1"
                        elif query_type == 'string':
                            # strip newline chars
                            if query_name.lower().find("removeblanks") != -1:
                                cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                                cmp_computation.set('name', variable_name)
                                cmp_computation.set('resultType', 'text')
                                cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')

                                # we expect only 1 parameter is declared
                                parameter = data.find("Parameters/Parameter").get('ref')
                                cmp_computation_script.text = "REPLACE(" + parameter + ", \"\\r\", \", \")"

                                variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1
                            else:
                                # add support to TRIM calculations on UTQ variables
                                if query_name.lower().find("trim") != -1:
                                    cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                                    cmp_computation.set('name', variable_name)
                                    cmp_computation.set('resultType', 'text')
                                    cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')

                                    # we expect only 1 parameter is declared
                                    if data.find("Parameters/Parameter") is not None:
                                        parameter = data.find("Parameters/Parameter").get('ref')
                                        cmp_computation_script.text = "TRIM(" + parameter + ")"

                                        variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1
                                    else:
                                        # we add dummy text
                                        cmp_computation_script.text = variable_name

                                        error_msg = error_msg + "Missing parameter for TRIM operation on " + query_name + "\n"
                                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                else:
                                    # create dummy variable
                                    cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                                    cmp_computation.set('name', variable_name)
                                    cmp_computation.set('resultType', 'text')
                                    cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')

                                    cmp_computation_script.text = variable_name

                                    variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1
                                    error_msg = error_msg + "Unsupported Calculation string manipulation at " + query_id + "\n"
                        else:
                            variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1
                            error_msg = error_msg + "Unsupported Calculation return type at " + query_id + "\n"

                        # add the variable name into search string
                        cond_search_str[variable_name] = variable_name

            elif variable_type == "DynamicMultipleChoiceQuestion":
                # DMCQ derives source mostly from CALC
                layout = data.get("Layout") or ""
                priority = data.get("Priority") or ""
                topic = data.find("Topic").text
                question = data.find("Question").text
                response_source = data.find("ResponseSource").get("ref")
                device = data.get("Device") or ""
                multiple_select_toggle = data.get("MultipleSelectToggle") or ""

                variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1

            else:
                variables["Stats"]["unknown"] = int(variables["Stats"]["unknown"]) + 1
                error_msg = error_msg + "Unsupported variable at " + query_id + "\n"

        elif logic_variable.tag == "Condition":
            # Condition in Hotdocs are calculations that have boolean return value
            if query_details[1].tag == "Repeater":
                data = query_details[2]
            else:
                data = query_details[1]

            variable_type = data.tag

            if variable_type == "Calculation":
                variable_name = query_name
                variable_name = variable_name.replace('.', '_')

                # @note Hotdocs has maximum lenght of 100 for variable name
                if len(variable_name) > 99:
                    error_msg = error_msg + "Maximum variable name length on " + query_name + "\n"
                    variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                else:
                    # check if there is already a variable with the same name
                    if variable_name in cond_search_str:
                        error_msg = error_msg + variable_name + " already exists, see " + query_id + "\n"
                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                    else:
                        cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                        cmp_computation.set('name', variable_name)
                        cmp_computation.set('resultType', 'trueFalse')
                        cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')

                        script_data = ""
                        if data.find("Parameters/Parameter") is not None:
                            param_ref = data.find("Parameters/Parameter").get('ref')
                            param_name = data.find("Parameters/Parameter").get('name')

                        param_script = data.find("script").text
                        script_data = param_script.replace(param_name, param_ref)

                        cmp_computation_script.text = script_data

                        variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

                        # add the variable name into search string
                        cond_search_str[variable_name] = variable_name

            elif variable_type == "ConditionExpression":
                # @action should be the same with Exari to Hotdocs templater
                variable_name = query_name.replace('.', '_')
                variable_name = variable_name.replace('-', '_')

                # @note Hotdocs has maximum lenght of 100 for variable name
                if len(variable_name) > 99:
                    error_msg = error_msg + "Maximum variable name length on " + query_name + "\n"
                    variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                else:
                    # deal with multiple conditions, negation condition, or simple variable value test
                    stack1 = []
                    stack2 = []

                    # depth first elem parsing
                    for sub_elem in data.iter():
                        if sub_elem.tag == "ConditionExpression":
                            # do not add the root elem
                            pass
                        elif (sub_elem.tag == "Test") or (sub_elem.tag == "UseCondition"):
                            stack1.append(sub_elem)
                        else:
                            # track condition operators on different stack
                            stack1.append(sub_elem.tag)

                    # create infix notation using postfix stack structure
                    condition_expr = ""
                    derived_variable_name = ""
                    if len(stack1) == 1:
                        # stack 1 contains simple condition ie. generated from MCQ
                        operator = stack1.pop()
                        if isinstance(operator, ET.Element):
                            # for Test elems, strip periods on variable name
                            if operator.tag == 'Test':
                                variable_name = operator.get('IDREF')
                                variable_name = variable_name.replace('.', '_')
                                variable_name = variable_name.replace(' ', '')

                                variable_value = operator.get('Value')
                                if variable_value is not None:
                                    condition_expr = variable_name +" = \""+ variable_value+"\""

                                    variable_value = variable_value.replace(' ', '')
                                    derived_variable_name = variable_name + "_" + variable_value

                                    if len(derived_variable_name) > 100:
                                        derived_variable_name = query_name
                                        derived_variable_name = derived_variable_name.replace('.', '_')
                                        derived_variable_name = derived_variable_name.replace('-', '_')
                                else:
                                    variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                    error_msg = error_msg + "Value required at condition " + query_id + "\n"
                            elif operator.tag == 'UseCondition':
                                # this is probably derived condition
                                operand_name = operator.get('IDREF')
                                operand_name = operand_name.replace('.', '_')
                                condition_expr = "IF "+operand_name+" RESULT TRUE END IF"

                                variable_name = query_name.replace('.', '_')
                                variable_name = variable_name.replace('-', '_')
                            else:
                                variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                error_msg = error_msg + "Unsupported ConditionExpression at " + query_id + "\n"

                            stack2.append(condition_expr)
                    else:
                        while len(stack1) > 0:
                            # stack 1 contains compound condition
                            operator = stack1.pop()
                            if isinstance(operator, ET.Element):
                                # put Test and UseCondition elems on the temp stack
                                stack2.append(operator)
                            else:
                                if operator == "Not":
                                    # handling negation operation
                                    if len(stack2) > 0:
                                        operand1 = stack2.pop()
                                        # stack 2 contains elems as operands or assembled conditions
                                        if isinstance(operand1, ET.Element):
                                            if operand1.tag == "UseCondition":
                                                condition_expr = operand1.get('IDREF')
                                                # period in condition expression variable name may come from
                                                # autogenerated MCQ options or user provided variable names
                                                condition_expr = condition_expr.replace('.', '_')
                                                condition_expr = condition_expr.replace('-', '_')
                                            elif operand1.tag == "Test":

                                                # for Test elems, strip periods on variable name
                                                variable_name = operand1.get('IDREF')
                                                variable_name = variable_name.replace('.', '_')
                                                variable_value = operand1.get('Value')

                                                derived_variable_name = query_name
                                                derived_variable_name = query_name.replace('.', '_')

                                                cond_var_data_type = lgc_root.findall("./LogicSetup/Variables/Variable[@name='" + variable_name + "']")
                                                if cond_var_data_type == "string" or cond_var_data_type == "NonEmptyString":
                                                    if variable_value is not None:
                                                        condition_expr = "("+variable_name+" = \""+variable_value+"\")"
                                                    else:
                                                        condition_expr = "("+variable_name+" = \"\")"

                                                    condition_expr = "ANSWERED("+ variable_name +") AND " + condition_expr
                                                else:
                                                    condition_expr = "ANSWERED("+ variable_name +")"

                                            else:
                                                variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                                error_msg = error_msg + "Unexpected element while processing ConditionExpression at " + query_id + "\n"
                                        else:
                                            # temp stack contains assembled conditions
                                            condition_expr = operand1

                                        condition_expr = "(NOT " + condition_expr + ")"

                                        stack2.append(condition_expr)
                                    else:
                                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                        error_msg = error_msg + "Missing operand for NOT condition on " + query_id + "\n"
                                else:
                                    # we are now handling compound conditions
                                    # only UseCondition elems should only be processed here
                                    if len(stack2) > 1:
                                        operand1 = stack2.pop()
                                        operand2 = stack2.pop()

                                        operand_name = ""
                                        operand_value = ""
                                        # conditions expressions generated from MCQ needs to be renamed
                                        if isinstance(operand1, ET.Element):
                                            if operand1.tag == "UseCondition":
                                                operand1 = operand1.get('IDREF')
                                                operand1 = operand1.replace('.', '_')
                                                operand1 = operand1.replace('-', '_')
                                            elif operand1.tag == "Test":
                                                # for Test elems, strip periods on variable name
                                                operand_name = operand1.get('IDREF').replace('.', '_')
                                                operand_value = operand1.get('Value')
                                                if operand_value is not None:
                                                    operand1 = "("+operand_name+" = \""+operand_value+"\")"
                                                else:
                                                    # some Test elems contains UTQs
                                                    operand1 = operand_name

                                        if isinstance(operand2, ET.Element):
                                            if operand2.tag == "UseCondition":
                                                operand2 = operand2.get('IDREF')
                                                operand2 = operand2.replace('.', '_')
                                                operand2 = operand2.replace('-', '_')
                                            elif operand2.tag == "Test":
                                                # for Test elems, strip periods on variable name
                                                operand_name = operand2.get('IDREF').replace('.', '_')
                                                operand_value = operand2.get('Value')
                                                if operand_value is not None:
                                                    operand2 = "("+operand_name+" = \""+operand_value+"\")"
                                                else:
                                                    # some Test elems contains UTQs reference
                                                    operand2 = operand_name

                                        condition_expr = "(" + operand1 + " " + operator.upper() + " " + operand2 + ")"
                                        stack2.append(condition_expr)

                                        variable_name = query_name
                                        variable_name = variable_name.replace('.', '_')
                                        variable_name = variable_name.replace('-', '_')
                                    else:
                                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                                        error_msg = error_msg + "Incomplete operands for " + operator +" on " + query_id + "\n"

                    if derived_variable_name != "":
                        variable_name = derived_variable_name

                    # check if there is already a variable with the same name
                    if variable_name in cond_search_str:
                        error_msg = error_msg + variable_name + " already exists, see " + query_id + "\n"
                        variables[variable_type]["stats"]["error"] = int(variables[variable_type]["stats"]["error"]) + 1
                    else:
                        cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                        cmp_computation.set('name', variable_name)
                        cmp_computation.set('resultType', 'trueFalse')
                        cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')

                        # temp stack should contain the final condition
                        condition_expr = stack2.pop()
                        cmp_computation_script.text = condition_expr

                        # add the variable name into search string
                        cond_search_str[variable_name] = variable_name

                        variables[variable_type]["stats"]["total"] = int(variables[variable_type]["stats"]["total"]) + 1

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

                variable_name = query_name
                variable_name = variable_name.replace('.', '_')
                # create placeholder variable
                cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                cmp_computation.set('name', variable_name)
                cmp_computation.set('resultType', 'number')
                cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                cmp_computation_script.text = "1"

            elif variable_type == "Calculation":
                pass_repeat_index = data.get("PassRepeatIndex") or ""

                #@todo strip whitespaces
                script = data.find("script").text or ""
                explanatory_blurb = data.find("ExplanatoryBlurb") or ""
                parameters = data.find("Parameters")

                variable_name = query_name
                variable_name = variable_name.replace('.', '_')
                # create placeholder variable
                cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                cmp_computation.set('name', variable_name)
                cmp_computation.set('resultType', 'number')
                cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                cmp_computation_script.text = "1"

            elif variable_type == "IncrementingRepeat":
                topic = data.find("Topic").text
                question = data.find("Question").text

                variable_name = query_name
                variable_name = variable_name.replace('.', '_')
                # create placeholder variable
                cmp_computation = ET.SubElement(cmp_components, '{'+namespace+'}computation')
                cmp_computation.set('name', variable_name)
                cmp_computation.set('resultType', 'number')
                cmp_computation_script = ET.SubElement(cmp_computation, '{'+namespace+'}script')
                cmp_computation_script.text = "1"

            # repeats in Hotdocs are controlled by Dialog variables so we only need this info for stats
            variables[variable_type]["stats"]["ignored"] = int(variables[variable_type]["stats"]["ignored"]) + 1

    # group together relevant variables
    for topic in variables["Data"].keys():
        # remove special chars
        variable_name = topic
        variable_name = variable_name.replace(',','')
        variable_name = variable_name.replace('\'','')
        variable_name = variable_name.replace('/','')
        variable_name = variable_name.replace('-','')
        variable_name = variable_name.replace('(','')
        variable_name = variable_name.replace(')','')
        variable_parts = variable_name.split(' ')

        variable_name = ""
        for part in variable_parts:
            variable_name = variable_name + part.capitalize()

        variable_name = variable_name + "DI"

        cmp_dialog = ET.SubElement(cmp_components, '{'+namespace+'}dialog')
        cmp_dialog.set('name', variable_name)
        cmp_dialog.set('showChildButtons', 'false')
        cmp_dialog_title = ET.SubElement(cmp_dialog, '{'+namespace+'}title')
        cmp_dialog_title.text = topic
        cmp_dialog_contents = ET.SubElement(cmp_dialog, '{'+namespace+'}contents')

        # sorting using python's native sorted() on dict items gives inconsistent results
        iteration_keys = list(variables["Data"][topic].keys())

        for key in iteration_keys:
            cmp_dialog_contents_item = ET.SubElement(cmp_dialog_contents, '{'+namespace+'}item')
            cmp_dialog_contents_item.set('name', variables["Data"][topic][key]["Name"])

        cmp_dialog_prompt_position = ET.SubElement(cmp_dialog, '{'+namespace+'}promptPosition')
        cmp_dialog_prompt_position.set('type', 'left')
        cmp_dialog_prompt_position.set('maxUnits', '30')

    # create a new XML file with the results
    tree = ET.ElementTree(cmp_root)

    variables["Stats"]["ignored"] = int(variables["MultipleChoiceQuestion"]["stats"]["ignored"]) + \
        int(variables["UserTextQuestion"]["stats"]["ignored"]) + int(variables["Calculation"]["stats"]["ignored"]) + \
        int(variables["DynamicMultipleChoiceQuestion"]["stats"]["ignored"]) + int(variables["ConditionExpression"]["stats"]["ignored"]) + \
        int(variables["SmartPhrase"]["stats"]["ignored"]) + int(variables["Repeat"]["stats"]["ignored"])

    variables["Stats"]["error"] = int(variables["MultipleChoiceQuestion"]["stats"]["error"]) + \
        int(variables["UserTextQuestion"]["stats"]["error"]) + int(variables["Calculation"]["stats"]["error"]) + \
        int(variables["DynamicMultipleChoiceQuestion"]["stats"]["error"]) + int(variables["ConditionExpression"]["stats"]["error"]) + \
        int(variables["SmartPhrase"]["stats"]["error"]) + int(variables["Repeat"]["stats"]["error"])

    json_directory = Path(Path.cwd(), "json")
    report_directory = Path(Path.cwd(), "report")
    if not json_directory.exists():
        # create the directory but raise alarms if it does not exist
        json_directory.mkdir(parents=False, exist_ok=False)

    if not report_directory.exists():
        # create the directory but raise alarms if it does not exist
        report_directory.mkdir(parents=False, exist_ok=False)

    json_file_name = Path(json_directory, str(Path(logic_file).stem + '.json').lower())
    with open(json_file_name, 'w') as f:
        json.dump(variables, f, indent=4)

    report_file_name = Path(report_directory, str(Path(logic_file).stem + '.txt').lower())
    report_file = open(report_file_name,"w")
    report_file.write(error_msg)
    report_file.close()

    return tree

# specify allowed command line arguments
argument_parser = argparse.ArgumentParser()

argument_parser.add_argument("-o", "--output", help = "Specify output directory")
argument_parser.add_argument("-i", "--input", help = "Specify input file")

# @note command line arguments are part of the namespace
args = argument_parser.parse_args()

cmp_logic_contents = None

if args.input:
    input_logic_file = args.input
    if Path(input_logic_file).suffix.lower() == ".lgc":
        # return value is type <ElementTree>
        cmp_logic_contents = convert_logic_file( input_logic_file )

        output_directory = ""
        if args.output:
            output_directory = Path(args.output)
        else:
            output_directory = Path(Path.cwd(), "output")

        if not output_directory.exists():
            # create the directory but raise alarms if it does not exist
            output_directory.mkdir(parents=False, exist_ok=False)

        base_name = Path(input_logic_file).stem
        cmp_file_name = base_name + '.cmp'
        cmp_file_path = Path(output_directory, cmp_file_name)

        #@see https://stackoverflow.com/questions/15356641/how-to-write-xml-declaration-using-xml-etree-elementtree
        cmp_logic_contents.write(cmp_file_path, encoding='utf-8', xml_declaration=True, method = 'xml')
    else:
        print("Invalid input file")

else:
    print("Please specify input file. See logic_parser.exe -h for details")



