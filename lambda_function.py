import json
import boto3
import urllib3
import os
from datetime import datetime

def lambda_handler(event, context):
    print("event Started")
    print("=========================")
    print(event)
    request = json.loads(event['body'])
    auth_key = os.environ['ESIM_GO_AUTH_KEY']
    messages = []

    if request['alertType'] == 'Utilisation':
        # The ICCID you want to find and update
        iccid_to_find = request['iccid']
        
        # Initialize a list to store matching items
        is_item_matched = False

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('esim_details')
        response = table.scan()
        items = response.get('Items', [])

        # Iterate through the items and search for the ICCID
        for item in items:
            esim_details = item.get('esim_details', {})

            for index, esim_detail in enumerate(esim_details):
                print(esim_detail)
                if esim_detail['iccid'] == iccid_to_find:
                    esim_details[index]['initialQuantity'] = str(request['bundle']['initialQuantity'])
                    esim_details[index]['remainingQuantity'] = str(request['bundle']['remainingQuantity'])
                    esim_details[index]['startTime'] = request['bundle']['startTime']
                    esim_details[index]['endTime'] = request['bundle']['endTime']
                    
                    # Initialize sentMessages field if not present
                    if 'sentMessages' not in esim_details[index]:
                        esim_details[index]['sentMessages'] = []
                    
                    is_item_matched = True
                    print("ICCID Found in table")
                    break
            
            if is_item_matched:
                update_expression = "SET esim_details = :esim_details"
                expression_attribute_values = {":esim_details": esim_details}
                
                # Perform the update with the correct data types for the primary key
                response = table.update_item(
                    Key={'esim_order_id': item['esim_order_id']},  # Remove the data type specifier
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_attribute_values
                )
                print("Usage details updated in db")
                print(response)
                break

        initial_quantity = request['bundle']['initialQuantity']
        remaining_quantity = request['bundle']['remainingQuantity']
        used_quantity = initial_quantity - remaining_quantity
        print(used_quantity)
        
        # Check if the bundle name contains 'esim_UL_'
        if 'esim_UL_' in request['bundle']['name']:
            print("Unlimited bundle detected. Skipping SMS notification.")
            messages.append('Usage details updated for unlimited bundle')
            return {
                'statusCode': 200,
                'body': json.dumps(messages)
            }
        
        # Calculate percentages
        percent_1 = (initial_quantity * 0.01)
        percent_50 = (initial_quantity * 0.50)
        percent_80 = (initial_quantity * 0.80)

        print(percent_1, percent_50, percent_80, remaining_quantity)
        message = ""
        
        if used_quantity == initial_quantity:
            print("100% usage reached.")
            message = "You’ve used all the data on your eSIM - if you’d like to top it up please visit https://easyesim.co/pages/top-ups"
        elif used_quantity >= percent_80:
            print("80% usage reached.")
            message = "You’ve used 80% of the data on your eSIM - if you’d like to top it up please visit https://easyesim.co/pages/top-ups"
        elif used_quantity >= percent_50:
            print("50% usage reached.")
            message = "You’ve used 50% of the data on your eSIM - you can keep an eye on usage at https://easyesim.co/pages/esim-usage"
        
        if message != '':
            # Create an instance of urllib3 PoolManager
            http = urllib3.PoolManager()

            url = 'https://api.esim-go.com/v2.3/esims/' + request['iccid'] + '/sms'
            payload = {
                "message": message,
                "from": "eSIM"
            }
            headers = {"X-API-Key": auth_key}
            r = http.request('POST', url, body=json.dumps(payload), headers=headers)
            response_text = r.data.decode('utf-8')
            print(response_text)
            messages.append(response_text)

            # Add sent message details to the database
            current_time = datetime.utcnow().isoformat() + 'Z'
            sent_message_details = {
                "message": message,
                "dateTime": current_time
            }
            
            for item in items:
                esim_details = item.get('esim_details', {})
                for index, esim_detail in enumerate(esim_details):
                    if esim_detail['iccid'] == iccid_to_find:
                        esim_details[index]['sentMessages'].append(sent_message_details)
                        update_expression = "SET esim_details = :esim_details"
                        expression_attribute_values = {":esim_details": esim_details}
                        
                        # Perform the update with the correct data types for the primary key
                        response = table.update_item(
                            Key={'esim_order_id': item['esim_order_id']},  # Remove the data type specifier
                            UpdateExpression=update_expression,
                            ExpressionAttributeValues=expression_attribute_values
                        )
                        print("Sent message details updated in db")
                        print(response)
                        break

    elif request['alertType'] == 'FirstAttachment':
        print("FirstAttachment")
        
        # Create an instance of urllib3 PoolManager
        http = urllib3.PoolManager()
        url = 'https://api.esim-go.com/v2.3/esims/' + request['iccid'] + '/sms'
        payload = {
            "message": "Your eSIM has been set up correctly, good work! Remember to switch data roaming on for your eSIM and off for your existing SIM when you travel.",
            "from": "eSIM"
        }
        headers = {"X-API-Key": auth_key}
        r = http.request('POST', url, body=json.dumps(payload), headers=headers)
        response_text = r.data.decode('utf-8')
        print(response_text)
        messages.append(response_text)

        # Add sent message details to the database
        current_time = datetime.utcnow().isoformat() + 'Z'
        sent_message_details = {
            "message": payload['message'],
            "dateTime": current_time
        }
        
        for item in items:
            esim_details = item.get('esim_details', {})
            for index, esim_detail in enumerate(esim_details):
                if esim_detail['iccid'] == request['iccid']:
                    esim_details[index]['sentMessages'].append(sent_message_details)
                    update_expression = "SET esim_details = :esim_details"
                    expression_attribute_values = {":esim_details": esim_details}
                    
                    # Perform the update with the correct data types for the primary key
                    response = table.update_item(
                        Key={'esim_order_id': item['esim_order_id']},  # Remove the data type specifier
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=expression_attribute_values
                    )
                    print("Sent message details updated in db")
                    print(response)
                    break

    # Return the response text as part of the response
    return {
        'statusCode': 200,
        'body': json.dumps({
            'messages': messages,
            'response_text': response_text
        })
    }
