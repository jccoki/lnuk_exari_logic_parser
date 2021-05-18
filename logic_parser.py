import xml.etree.ElementTree as ET
import json

tree = ET.parse('NewWAM.lgc')

root = tree.getroot()

variables = {}
variables["MultipleChoiceQuestion"] = {}
variables["UserTextQuestion"] = {}
variables["Calculation"] = {}
variables["DynamicMultipleChoiceQuestion"] = {}

# fetch all logic variable elems
logic_variables = root.findall("./LogicSetup/Variables/")
for logic_variable in logic_variables:
    # fetch non boolean variables
    if logic_variable.tag == "Variable":
        #child.attrib  
        query_id = logic_variable.get('query')
        query_name = logic_variable.get('name')
        query_type = logic_variable.get('type')
        query_details = root.find("./LogicSetup/Queries/Query[@name='" + query_id + "']")
        
        # if variable has repeater, repeater elem becomes the second child elem
        # else the second child element determines the variable type
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

            variables[variable_type][query_id] = {}
            variables[variable_type][query_id].update({"Name":query_name, "DataType":query_type, "Layout":layout, "Priority":priority, "Topic":topic, "Question":question})
            variables[variable_type][query_id]["Responses"] = {}

            responses = data.find("Responses")        
            for response in responses:
                # prompts in some variables in NewWAM were wrapped with <p>
                if response.find("Prompt/p") is not None:
                    prompt = response.find("Prompt/p").text
                else:
                    prompt = response.find("Prompt").text

                value = response.find("SetValueTo").text
                variables[variable_type][query_id]["Responses"].update({value:prompt})

        elif variable_type == "UserTextQuestion":
            layout = data.get("Layout") or ""
            priority = data.get("Priority") or ""
            rows = data.get("Rows") or ""
            columns = data.get("Columns") or ""
            topic = data.find("Topic").text
            question = data.find("Question").text

            example_text = ""
            if data.find("ExampleText") is not None:
                example_text = data.find("ExampleText").text

            default_text_data = ""
            if data.find("DefaultText") is not None:
                default_text = data.find("DefaultText")

                # do not process default text that contains mixed text node and sub elems
                # only process text OR single InsertVariable sub elem
                # we do not process ConditionalPhrase due to the same mixed text node and InsertVariable issue
                # report those UserTextQuestion that contains ConditionalPhrase or multiple sub elems
                sub_elem_count = len(list(default_text))
                if default_text.text is not None and sub_elem_count == 0:
                    default_text_data = default_text.text
                elif default_text.text is None and sub_elem_count > 0:
                    if(default_text.find("ConditionalPhrase")) is not None:
                        default_text_data = "Unsupported default text sub element"
                    else:
                        default_text_data = "IDREF:" + default_text.find("InsertVariable").get("IDREF")
                else:
                    pass

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
            pass_repeat_index = data.get("PassRepeatIndex")
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

                # items to be added should be key:val pair else only the last in the list will be added
                variables[variable_type][query_id]["Parameters"].update({parameter_name:parameter_ref})

            #@todo process calculation as condition/boolean logic variables
            # calculation as condition is declared as Condition elem
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
            pass
    elif logic_variable.tag == "Condition":
        pass

with open('data.json', 'w') as f:
    json.dump(variables, f, indent=4)

