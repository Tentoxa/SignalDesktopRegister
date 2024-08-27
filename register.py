import os
import subprocess
import time
import re
import struct
import tarfile
import zipfile
from typing import Optional

import jdk
import requests
from github import Github
from tqdm import tqdm
from jdk.enums import OperatingSystem

from PIL import Image
from colorama import init, Fore, Style

try:
    from pyzbar.pyzbar import decode
except:
    print("Please install the required dependencies by running 'pip install -r requirements.txt'")
    print("IF YOU STILL ENCOUNTER ISSUES, PLEASE INSTALL THE FOLLOWING:")
    print("https://www.microsoft.com/en-gb/download/details.aspx?id=40784")
    exit(1)

# Initialize colorama for cross-platform colored output
init()

class Logger:
    @staticmethod
    def log(message: str, color: str = Fore.WHITE) -> None:
        print(f"{color}[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}{Style.RESET_ALL}")

class GithubUtils:
    def __init__(self):
        self.github = Github()

    def get_latest_release(self, repo_name: str) -> Optional[object]:
        repo = self.github.get_repo(repo_name)
        latest_release = repo.get_latest_release()
        for asset in latest_release.get_assets():
            if asset.name.endswith(".tar.gz") and "linux" not in asset.name.lower():
                return asset
        return None

    @staticmethod
    def download_asset(asset: object, download_path: str) -> Optional[str]:
        download_url = asset.browser_download_url
        response = requests.get(download_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        if response.status_code == 200:
            with open(download_path, 'wb') as f, tqdm(
                    desc=asset.name,
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))
            return download_path
        else:
            Logger.log(f"Failed to download {asset.name}: {response.status_code}", Fore.RED)
            return None


class FileUtils:
    @staticmethod
    def get_name_without_extension(filepath: str) -> str:
        base = os.path.basename(filepath)
        pattern = r'(\.tar\.gz|\.tar\.bz2|\.zip|\.rar|\.7z)$'
        return re.sub(pattern, '', base)

    @staticmethod
    def extract_tar_gz(file_path: str, extract_to: str, folder_name: Optional[str] = None) -> None:
        Logger.log(f"Extracting {file_path}")
        if folder_name:
            extract_to = os.path.join(extract_to, folder_name)
        os.makedirs(extract_to, exist_ok=True)
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(path=extract_to)
        Logger.log(f"Extraction complete to {extract_to}")

    @staticmethod
    def extract_zip(file_path: str, extract_to: str, folder_name: Optional[str] = None) -> None:
        Logger.log(f"Extracting {file_path}")

        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            first_folder = zip_ref.namelist()[0].split('/')[0]  # Get the first folder name

            # If a specific folder_name is given, it should be used instead of the first folder in the ZIP
            if folder_name:
                extract_to = os.path.join(extract_to, folder_name)
            else:
                extract_to = os.path.join(extract_to, first_folder)

            # Check if the folder already exists
            if os.path.exists(extract_to):
                Logger.log(f"Extraction aborted: {first_folder} already exists.")
                return

            os.makedirs(extract_to, exist_ok=True)
            zip_ref.extractall(extract_to)
            Logger.log(f"Extraction complete to {extract_to}")

    @staticmethod
    def find_cli_jar(dir: str) -> Optional[str]:
        for root, _, files in os.walk(dir):
            for file in files:
                if file.endswith(".jar") and os.path.basename(file).startswith("signal-cli"):
                    return os.path.join(root, file)
        return None


class JavaUtils:
    @staticmethod
    def get_java_version_of_file(jar_path: str) -> Optional[int]:
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                for file_name in jar.namelist():
                    if file_name.endswith('.class'):
                        with jar.open(file_name) as class_file:
                            header = class_file.read(8)
                            if len(header) < 8:
                                continue
                            magic, _, major_version = struct.unpack('>IHH', header)
                            if magic != 0xCAFEBABE:
                                continue
                            return major_version
        except Exception as e:
            Logger.log(f"Error reading JAR file: {e}")
            return None

    @staticmethod
    def java_version_from_major(major_version: int) -> str:
        version_mapping = {
            45: "Java 1.1", 46: "Java 1.2", 47: "Java 1.3", 48: "Java 1.4",
            49: "Java 5", 50: "Java 6", 51: "Java 7", 52: "Java 8",
            53: "Java 9", 54: "Java 10", 55: "Java 11", 56: "Java 12",
            57: "Java 13", 58: "Java 14", 59: "Java 15", 60: "Java 16",
            61: "Java 17", 62: "Java 18", 63: "Java 19", 64: "Java 20",
            65: "Java 21", 66: "Java 22", 67: "Java 23", 68: "Java 24",
            69: "Java 25", 70: "Java 26", 71: "Java 27", 72: "Java 28",
            73: "Java 29", 74: "Java 30",
        }
        return version_mapping.get(major_version, "Unknown Java version")

    @staticmethod
    def download_openjdk(version: str, download_path: str) -> Optional[str]:
        version = re.sub(r'\D', '', version)
        download_url = jdk.get_download_url(str(version), vendor="Corretto", operating_system=OperatingSystem.WINDOWS)

        if download_url is None:
            Logger.log(f"Could not find OpenJDK {version} download URL")
            return None

        download_path = os.path.join(download_path, f"openjdk-{version}.zip")

        if os.path.exists(download_path):
            Logger.log(f"OpenJDK {version} already downloaded")
            return download_path

        response = requests.get(download_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        if response.status_code == 200:
            with open(download_path, 'wb') as f, tqdm(
                    desc=f"OpenJDK {version}",
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))
            Logger.log(f"Downloaded OpenJDK {version} successfully")
            return download_path
        else:
            Logger.log(f"Failed to download OpenJDK {version}: {response.status_code}")
            return None


class SignalCLISetup:
    def __init__(self, dependencies_directory: str):
        self.dependencies_directory = dependencies_directory
        self.github_utils = GithubUtils()
        self.current_dir = os.path.dirname(os.path.realpath(__file__))
        self.dep_dir = os.path.join(self.current_dir, self.dependencies_directory)
        self.signal_cli_dir = os.path.join(self.dep_dir, "signal-cli")

    def setup(self) -> str:
        self.create_directories()
        latest_release = self.get_latest_release()
        if latest_release:
            zipped_path = self.download_signal_cli(latest_release)
            if zipped_path:
                signal_cli_path = self.extract_signal_cli(zipped_path)
                signal_cli_bat = os.path.join(signal_cli_path, "bin", "signal-cli.bat")
                java_path = self.check_and_setup_java()
                self.modify_batch_file(signal_cli_bat, java_path)

                if java_path:
                    Logger.log("Signal-cli setup complete", Fore.GREEN)
                    Logger.log(f"Signal-cli path: {signal_cli_bat}", Fore.CYAN)
                    Logger.log(f"Java path: {java_path}", Fore.CYAN)
                    return signal_cli_bat
                else:
                    Logger.log("Java setup failed", Fore.RED)
                    exit(1)

    def create_directories(self) -> None:
        Logger.log("Creating dependencies directory")
        os.makedirs(self.dep_dir, exist_ok=True)
        os.makedirs(self.signal_cli_dir, exist_ok=True)

    def get_latest_release(self) -> Optional[object]:
        Logger.log("Getting latest signal-cli release")
        return self.github_utils.get_latest_release("AsamK/signal-cli")

    def download_signal_cli(self, latest_release: object) -> Optional[str]:
        Logger.log("Downloading signal-cli")
        download_dir = os.path.join(self.dep_dir, latest_release.name)
        if os.path.exists(download_dir):
            Logger.log("Signal-cli already downloaded")
            return download_dir
        return self.github_utils.download_asset(latest_release, download_dir)

    def extract_signal_cli(self, zipped_path: str) -> str:
        zipped_name_without_extension = FileUtils.get_name_without_extension(zipped_path)
        final_signal_cli_dir = os.path.join(self.signal_cli_dir, zipped_name_without_extension)

        if os.path.exists(final_signal_cli_dir):
            Logger.log("Signal-cli already extracted")
            return final_signal_cli_dir
        else:
            Logger.log("Extracting signal-cli")
            FileUtils.extract_tar_gz(zipped_path, self.dep_dir, os.path.basename(self.signal_cli_dir))
            if not os.path.exists(final_signal_cli_dir):
                Logger.log("Failed to extract signal-cli")
                exit(1)

            # Return the final extracted directory path
            Logger.log("Signal-cli found and extracted successfully")
            return final_signal_cli_dir

    def modify_batch_file(self, batch_file_path, custom_java_exe):
        # Check if the batch file exists
        if not os.path.isfile(batch_file_path):
            print(f"Error: The file '{batch_file_path}' does not exist.")
            return

        # Read the batch file content
        with open(batch_file_path, 'r') as file:
            lines = file.readlines()

        # Define the line to replace
        original_line = 'set JAVA_EXE=%JAVA_HOME%/bin/java.exe\n'
        modified_line = f'set JAVA_EXE={custom_java_exe}\n'

        # Flag to track if the replacement was successful
        replaced = False

        # Modify the batch file content
        with open(batch_file_path, 'w') as file:
            for line in lines:
                if line == original_line:
                    file.write(modified_line)
                    replaced = True
                else:
                    file.write(line)

        # Print the result of the modification
        if replaced:
            Logger.log(f"Successfully modified '{batch_file_path}'.")
        else:
            Logger.log(f"Line not found. No changes made to '{batch_file_path}'.")

    def check_and_setup_java(self) -> Optional[str]:
        Logger.log("Checking for correct java version")
        java_file = FileUtils.find_cli_jar(self.signal_cli_dir)
        if java_file is None:
            Logger.log("Failed to find signal-cli jar")
            return None

        major_version = JavaUtils.get_java_version_of_file(java_file)
        if major_version is not None:
            java_version = JavaUtils.java_version_from_major(major_version)
            Logger.log(f"Java Version of File: {java_version}")

            Logger.log("Downloading OpenJDK")
            download_path = JavaUtils.download_openjdk(java_version, self.dep_dir)
            if not download_path:
                Logger.log("Failed to download OpenJDK")
                return None

            Logger.log("Extracting OpenJDK")
            # Check if the OpenJDK has already been extracted

            FileUtils.extract_zip(download_path, self.dep_dir, "openjdk")

            # Find the first directory in the extracted OpenJDK
            openjdk_dir = os.path.join(self.dep_dir, "openjdk")
            for root, dirs, _ in os.walk(openjdk_dir):
                if dirs:
                    openjdk_dir = os.path.join(root, dirs[0])
                    break

            Logger.log(f"Extracted OpenJDK")
            java_path = os.path.join(openjdk_dir, "bin", "java.exe")
            if os.path.exists(java_path):
                Logger.log(f"Java path: {java_path}")
                return java_path
            else:
                Logger.log(f"Java executable not found at expected path: {java_path}")
                return None
        else:
            Logger.log("Could not determine the Java version from the JAR file.")
            return None


class SignalCLIInteraction:
    def __init__(self, signal_cli_path: str, phone_number: str):
        self.signal_cli_path = signal_cli_path
        self.phone_number = phone_number

    def register(self, captcha: str) -> None:
        Logger.log("Registering Phone Number", Fore.YELLOW)
        command = f"{self.signal_cli_path} -u {self.phone_number} register --captcha {captcha}"
        result = subprocess.run(command, capture_output=True, text=True)
        error = result.stderr.strip()

        if "Failed to register" in error:
            Logger.log("Failed to register", Fore.RED)
            Logger.log(error, Fore.RED)
            exit(1)

        Logger.log("Successfully sent registration code", Fore.GREEN)

    def verify(self, code):
        if not code.isdigit():
            Logger.log("Invalid code", Fore.RED)
            exit(1)

        Logger.log("Verifying code", Fore.YELLOW)
        command = f"{self.signal_cli_path} -u {self.phone_number} verify {code}"
        result = subprocess.run(command, capture_output=True, text=True)
        error = result.stderr.strip()

        if "Verify error" in error:
            Logger.log("Failed to verify code", Fore.RED)
            Logger.log(error, Fore.RED)
            exit(1)

        Logger.log("Successfully verified the account", Fore.GREEN)

    def add_device(self, screenshot):
        if not os.path.exists(screenshot):
            Logger.log("Invalid path", Fore.RED)
            exit(1)

        img = Image.open(screenshot)
        result = decode(img)[0].data.decode()
        if not result:
            Logger.log("Failed to decode QR Code", Fore.RED)
            exit(1)

        Logger.log("Adding Device", Fore.YELLOW)
        command = f"""{self.signal_cli_path} -u {self.phone_number} addDevice --uri "{result}" """
        result = subprocess.run(command, capture_output=True, text=True)
        error = result.stderr.strip()

        if "invalid format" in error or "failed" in error:
            Logger.log("Failed to add device", Fore.RED)
            Logger.log(error, Fore.RED)
            exit(1)

        Logger.log("Successfully added device", Fore.GREEN)


if __name__ == "__main__":
    setup = SignalCLISetup("assets")
    batch_path = setup.setup()

    if not batch_path:
        Logger.log("Failed to setup signal-cli", Fore.RED)
        exit(1)

    os.system("cls")

    phone_number = input(f"{Fore.CYAN}Please enter your Phone Number (Including country code like +49):{Style.RESET_ALL} ").strip()
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    interaction = SignalCLIInteraction(batch_path, phone_number)

    os.system("cls" if os.name == "nt" else "clear")
    print(f"{Fore.YELLOW}https://signalcaptchas.org/registration/generate.html{Style.RESET_ALL}")
    captcha_link = input(f"{Fore.CYAN}Please solve the Signal Captcha and Enter the Link to open in APP (or 'skip' to skip):{Style.RESET_ALL} ").strip()
    if captcha_link.lower() != "skip":
        interaction.register(captcha_link)

    code = input(f"{Fore.CYAN}Please enter the code you received (or 'skip' to skip):{Style.RESET_ALL} ").strip()
    if code.lower() != "skip":
        interaction.verify(code)

    Logger.log("Account registered successfully!", Fore.GREEN)

    print(f"{Fore.YELLOW}Next step will add your Signal Desktop to the registered account.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Please open Signal Desktop and take a screenshot of the QR Code.{Style.RESET_ALL}")
    qr_path = input(f"{Fore.CYAN}Enter the path to the screenshot:{Style.RESET_ALL} ").strip().replace('"', '')
    interaction.add_device(qr_path)

    Logger.log("You should now be able to use Signal Desktop with your registered account.", Fore.GREEN)
    input("Press Enter to exit.")