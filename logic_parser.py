import xml.etree.ElementTree as ET
import json

tree = ET.parse('Confidentiality_agreement.lgc')

root = tree.getroot()

variables = {}
variables["MultipleChoiceQuestion"] = {}
variables["UserTextQuestion"] = {}
variables["Calculation"] = {}

# fetch all logic variable elems
logic_variables = root.findall("./LogicSetup/Variables/Variable")
for child in logic_variables:  
    #child.attrib  
    query_id = child.get('query')
    query_name = child.get('name')
    query_type = child.get('type')
    query_details = root.find("./LogicSetup/Queries/Query[@name='" + query_id + "']")
    
    # if variable has repeater, repeater elem becomes the second child elem
    # else the second child element determines the variable type
    if query_details[1].tag == "Repeater":
        data = query_details[2]
    else:
        data = query_details[1]

    variable_type = data.tag

    if variable_type == "MultipleChoiceQuestion":
        layout = data.get("Layout") or ""
        priority = data.get("Priority") or ""
        topic = data.find("Topic").text
        question = data.find("Question").text

        variables[variable_type][query_id] = {}
        variables[variable_type][query_id].update({"Layout":layout, "Priority":priority, "Topic":topic, "Question":question})
        variables[variable_type][query_id]["Responses"] = {}

        responses = data.find("Responses")        
        for response in responses:
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
                
        variables[variable_type][query_id] = {}
        variables[variable_type][query_id].update({"Layout":layout, "Priority":priority, "Topic":topic, "Question":question, "Rows":rows, "Columns":columns})

        #@todo study parsing defaulttext and exampletext

    elif variable_type == "Calculation":
        pass_repeat_index = data.get("PassRepeatIndex")
        script = data.find("script").text or ""
        explanatory_blurb = data.find("ExplanatoryBlurb") or ""
        parameters = data.find("Parameters")
        variables[variable_type][query_id] = {}
        variables[variable_type][query_id].update({"PassRepeatIndex":pass_repeat_index,"script":script, "ExplanatoryBlurb":explanatory_blurb})
        variables[variable_type][query_id]["Parameters"] = {}

        for parameter in parameters:
            parameter_name = data.get("name") or ""
            parameter_ref = data.get("ref") or ""
            variables[variable_type][query_id]["Parameters"].update({"name":parameter_name, "ref":parameter_ref})
        
        #@todo process calculation as condition/boolean logic variables
    else:
        pass

print(json.dumps(variables))
