#!/usr/bin/env python3
"""
ShareXpress CLI Tool
Command-line interface for the ShareXpress file sharing platform
"""

import argparse
import requests
import json
import os
import sys
from getpass import getpass

class ShareXpressCLI:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.auth_token = None

    def login(self, username, password):
        """Authenticate with the ShareXpress server"""
        try:
            # First get the main page to get session cookies
            self.session.get(f"{self.base_url}/")

            response = self.session.post(
                f"{self.base_url}/api/login",
                json={'username': username, 'password': password},
                headers={'Content-Type': 'application/json'}
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print("Login successful!")
                return True
            else:
                print(f"Login failed: Server returned {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False

        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to the server. Make sure it's running.")
            return False
        except Exception as e:
            print(f"Error during login: {str(e)}")
            return False

    def upload(self, file_path):
        """Upload a file to the server"""
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' does not exist.")
            return False

        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = self.session.post(
                    f"{self.base_url}/api/upload",
                    files=files
                )

            print(f"Upload Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Upload successful!")
                print(f"Download URL: {result.get('download_url')}")
                return True
            else:
                print(f"Upload failed: Server returned {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False

        except Exception as e:
            print(f"Error during upload: {str(e)}")
            return False

    def list_files(self):
        """List all files for the current user"""
        try:
            response = self.session.get(f"{self.base_url}/api/files")

            print(f"List Status Code: {response.status_code}")

            if response.status_code == 200:
                files = response.json().get('files', [])
                if files:
                    print("Your files:")
                    for file in files:
                        print(f"  - {file['original_filename']} (Uploaded: {file['upload_date']})")
                        print(f"    Download URL: {file['download_url']}")
                        print()
                else:
                    print("No files found.")
                return True
            else:
                print("Failed to retrieve file list.")
                print(f"Response: {response.text[:200]}...")
                return False

        except Exception as e:
            print(f"Error retrieving files: {str(e)}")
            return False

    def login_required_check(self):
        """Check if user is already logged in (simple check)"""
        # For now, we'll just return False to always prompt for login
        return False

def main():
    parser = argparse.ArgumentParser(description="ShareXpress CLI Tool")
    parser.add_argument('--url', default='http://localhost:8080',
                       help='Base URL of the ShareXpress server')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Login command
    login_parser = subparsers.add_parser('login', help='Login to your account')
    login_parser.add_argument('username', help='Your username')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a file')
    upload_parser.add_argument('file_path', help='Path to the file to upload')

    # List command
    subparsers.add_parser('list', help='List your files')

    args = parser.parse_args()

    cli = ShareXpressCLI(args.url)

    if args.command == 'login':
        password = getpass("Password: ")
        cli.login(args.username, password)

    elif args.command == 'upload':
        # Check if we need to login first
        if not cli.login_required_check():
            username = input("Username: ")
            password = getpass("Password: ")
            if not cli.login(username, password):
                return

        cli.upload(args.file_path)

    elif args.command == 'list':
        # Check if we need to login first
        if not cli.login_required_check():
            username = input("Username: ")
            password = getpass("Password: ")
            if not cli.login(username, password):
                return

        cli.list_files()

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
