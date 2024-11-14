import os
import sys

variables = ['API_PORT']

api_cors_config = {
  "origins": ["*"],
  "methods": ["OPTIONS", "GET"],
  "allow_headers": ["Authorization", "Content-Type"]
}

def checkEnv():
  for variable in variables:
      if variable not in os.environ:
          print(str(variable) + " environment variable not found")
          sys.exit()