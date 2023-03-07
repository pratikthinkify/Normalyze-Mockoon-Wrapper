import re
import requests
import json
import uuid

from bs4 import BeautifulSoup

paste = set(['xml version'])
ignore = set(['...']) #Todo add repeat blocks

REPEAT_BLOCK_START = "{{# repeat (faker 'datatype.number' 20) }}"
REPEAT_BLOCK_END = "{{/ repeat }}"

custom_templates = {
	
}

datatype_mocks_custom = {
	"ListAllMyBucketsResult.Buckets.Bucket.Name": "Fixed-Bucket-Name-{{faker 'datatype.string'}}"
}

datatype_mocks_default = {
	'timestamp': {
		'DEFAULT': "{{faker 'datatype.datetime'}}",
	},
	'string': {
		'DEFAULT': "{{faker 'datatype.string'}}",
		'NAME': "{{faker 'name.fullName'}}",
		'ID': "{{faker 'datatype.uuid'}}",
		'ARN': "arn:aws:s3:::{{faker 'datatype.uuid'}}-{{faker 'datatype.uuid'}}",
	},
	'boolean': {
		'DEFAULT': "{{faker 'date.past'}}",
	},
}


def get_url(api_category, api_name):
	url = f'https://docs.aws.amazon.com/{api_category}/latest/API/API_{api_name}.html'
	print(url)
	return url


def get_aws_response(url):
	response = requests.get(url)

	aws_response = ""

	if response.status_code == 200:
		soup = BeautifulSoup(response.content, 'html.parser')

		aws_response = soup.find('h2', text='Response Syntax').find_next_sibling('pre')
		aws_response = aws_response.text.strip()

		print(aws_response)
	else:
		print("Failed to retrieve the response syntax i.e. aws_response.")
	return aws_response


def get_reponse_elements_with_keyword(url, keyword='Array'):
	response = requests.get(url)
	array_elements = []

	if response.status_code == 200:
		soup = BeautifulSoup(response.content, 'html.parser')

		dl = soup.find('h2', text='Response Syntax').findNext('dl')
		print('############## $$$$$')
		print(dl)

		keys, values = [], []
		for dt in dl.findAll("dt"):
			keys.append(dt.text.strip())
		for dd in dl.findAll("dd"):
			values.append(dd.text.strip())

		print('############## $$$$$ keys')
		print(keys)
		print('############## $$$$$ values')
		print(values)

		for i in range(len(keys)):
			if keyword in values[i]:
				array_elements.append(keys[i])

		print('############## $$$$$ array_elements')
		print(array_elements)

	return array_elements


def convert_aws_to_mockoon_reponse(aws_response, array_keyword):
	mockoon_reponse = []
	stack = []
	aws_response = aws_response.split('\n')

	for i in range(len(aws_response)):
		if any(key in aws_response[i] for key in ignore):
			print('ignoree', aws_response[i])

		elif any(key in aws_response[i] for key in paste):
			mockoon_reponse.append(aws_response[i])
			print('pasteeee', aws_response[i])

		elif any(key in aws_response[i] for key in datatype_mocks_default.keys()):

			match = re.search("<(.*?)>", aws_response[i])
			extracted_aws_datatype = match.group(1)

			match = re.search(">(.*?)<", aws_response[i])
			extracted_datatype = match.group(1)
			datatype_mocks_custom_key = f'{".".join(stack)}.{extracted_aws_datatype}'

			datatype_mocks_default_key = f'{extracted_aws_datatype}.{extracted_datatype}'

			print('datatype_mocks_custom_key: ' + datatype_mocks_custom_key)
			print('datatype_mocks_default_key: ' + datatype_mocks_default_key)
			print('extracted_datatype: ' + extracted_datatype)

			if datatype_mocks_custom_key in datatype_mocks_custom:
				mockoon_reponse_line = aws_response[i].replace(extracted_datatype, datatype_mocks_custom[datatype_mocks_custom_key])
			elif extracted_aws_datatype in datatype_mocks_default[extracted_datatype]:
				mockoon_reponse_line = aws_response[i].replace(extracted_datatype, datatype_mocks_default[extracted_datatype][extracted_aws_datatype])
			else:
				mockoon_reponse_line = aws_response[i].replace(extracted_datatype, datatype_mocks_default[extracted_datatype]['DEFAULT'])

			mockoon_reponse.append(mockoon_reponse_line)
			print('datatype', aws_response[i])
			print('mockeddd', mockoon_reponse_line)

		elif re.search("</(.*?)>", aws_response[i]):
			stack.pop()
			if any(f'</{k}>' in aws_response[i] for k in array_keyword):
				mockoon_reponse.append(REPEAT_BLOCK_END)
			mockoon_reponse.append(aws_response[i])
			print('closingg', aws_response[i])

		elif re.search("<(.*?)>", aws_response[i]):
			match = re.search("<(.*?)>", aws_response[i])
			extracted_word = match.group(1)
			stack.append(extracted_word)
			mockoon_reponse.append(aws_response[i])
			if any(f'<{k}>' in aws_response[i] for k in array_keyword):
				mockoon_reponse.append(REPEAT_BLOCK_START)
			print('openingg', aws_response[i])

		print(f'{stack}\n')

	return '\n'.join(mockoon_reponse)


def add_response_to_config_file(api_endpoint, mockoon_response):
	with open('template.json', 'r') as file:
		route = json.load(file)
	route['uuid'] = str(uuid.uuid4())
	route['method'] = 'get'
	route['endpoint'] = api_endpoint
	route['responses'][0]['uuid'] = str(uuid.uuid4())
	route['responses'][0]['body'] = mockoon_response

	with open('config.json', 'r') as file:
		config = json.load(file)
	config['routes'].append(route)

	with open("config.json", "w") as file:
		file.write(json.dumps(config))

	print("Write successful")


def update_config_for_aws(enpoint_name, endpoint_category):
	url = get_url(endpoint_category, enpoint_name)
	print(f'url: {url}')

	aws_response = get_aws_response(url)
	print(f'aws_response:\n{aws_response}')

	array_datatypes = get_reponse_elements_with_keyword(url, 'Array')
	print(f'array_datatypes:\n{array_datatypes}')

	mockoon_response = convert_aws_to_mockoon_reponse(aws_response, array_datatypes)
	print(f'mockoon_response:\n{mockoon_response}')

	add_response_to_config_file(enpoint_name, mockoon_response)
	print(f'Completed!')


def main():

	with open('input.json', 'r') as file:
		input = json.load(file)

	print(type(input))

	for cloud in input:
		for endpoint in input[cloud]:
			update_config_for_aws(endpoint['name'], endpoint['category'])


if __name__ == '__main__':
	main() 




