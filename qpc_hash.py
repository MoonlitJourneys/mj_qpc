import hashlib
import qpc_reader
from qpc_base import args, CreateDirectory, PosixPath
from os import path, sep, getcwd


QPC_DIR = PosixPath(path.dirname(path.realpath(__file__))) + "/"
QPC_HASH_DIR = QPC_DIR + "hashes/"
CreateDirectory(QPC_HASH_DIR)


# Source: https://bitbucket.org/prologic/tools/src/tip/md5sum
def MakeHash(filename):
    md5 = hashlib.md5()
    try:
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
                md5.update(chunk)
        return md5.hexdigest()
    except FileNotFoundError:
        return ""
    
    
def MakeHashFromString(string: str):
    return hashlib.md5(string.encode()).hexdigest()


BASE_QPC_HASH_LIST = (
    "qpc.py",
    "qpc_base.py",
    "qpc_c_parser.py",
    "qpc_hash.py",
    "qpc_makefile.py",
    "qpc_parser.py",
    "qpc_reader.py",
    "qpc_visual_studio.py",
    "qpc_vpc_converter.py",
    "qpc_writer.py",
)
        
        
BASE_QPC_HASHES = {}
for file in BASE_QPC_HASH_LIST:
    BASE_QPC_HASHES[QPC_DIR + file] = MakeHash(QPC_DIR + file)


# could make these functions into a class as a namespace
# probably a class, to store hashes of files we've checked before
def CheckHash(project_path: str, file_list=None):
    project_hash_file_path = GetHashFilePath(project_path)
    project_dir = path.split(project_path)[0]
    
    if path.isfile(project_hash_file_path):
        hash_file = qpc_reader.ReadFile(project_hash_file_path)
        
        if not hash_file:
            return False
        
        for block in hash_file:
            if block.key == "commands":
                if not _CheckCommands(project_dir, block.items):
                    return False
                
            elif block.key == "hashes":
                if not _CheckFileHash(project_dir, block.items):
                    return False

            elif block.key == "dependencies":
                pass

            elif block.key == "project_dependencies":
                if not _CheckMasterFileDependencies(project_dir, block.items):
                    return False
                
            elif block.key == "files":
                if not file_list:
                    continue
                if not _CheckFiles(project_dir, block.items, file_list):
                    return False
                
            else:
                # how would this happen
                block.Warning("Unknown Key in Hash: ")

        print("Valid: " + project_path + GetHashFileExt(project_path) + "\n")
        return True
    else:
        if args.verbose:
            print("Hash File does not exist")
        return False
    
    
def GetOutDir(project_hash_file_path):
    if path.isfile(project_hash_file_path):
        hash_file = qpc_reader.ReadFile(project_hash_file_path)
        
        if not hash_file:
            return ""

        commands_block = hash_file.GetItem("commands")
        
        working_dir = commands_block.GetItemValues("working_dir")[0]
        out_dir = commands_block.GetItemValues("out_dir")[0]
        return path.normpath(working_dir + "/" + out_dir)
    
    
def _CheckCommands(project_dir: str, command_list) -> bool:
    for command_block in command_list:
        if command_block.key == "working_dir":
            directory = getcwd()
            if project_dir:
                directory += sep + project_dir
            if directory != path.normpath(command_block.values[0]):
                return False
        
        elif command_block.key == "out_dir":
            pass
        
        elif command_block.key == "add":
            if sorted(args.add) != sorted(command_block.values):
                return False
        
        elif command_block.key == "remove":
            if sorted(args.remove) != sorted(command_block.values):
                return False
        
        elif command_block.key == "types":
            if sorted(args.types) != sorted(command_block.values):
                return False
        
        elif command_block.key == "macros":
            if sorted(args.macros) != sorted(command_block.values):
                return False
        
        else:
            command_block.Warning("Unknown Key in Hash: ")
    return True
    
    
def _CheckFileHash(project_dir, hash_list):
    for hash_block in hash_list:
        if path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = path.normpath(hash_block.values[0])
        else:
            project_file_path = path.normpath(project_dir + sep + hash_block.values[0])
        
        if hash_block.key != MakeHash(project_file_path):
            if args.verbose:
                print("Invalid: " + hash_block.values[0])
            return False
    return True


def _CheckMasterFileDependencies(project_dir, dependency_list):
    for script_path in dependency_list:
        if path.isabs(script_path.key) or not project_dir:
            project_file_path = path.normpath(script_path.key)
        else:
            project_file_path = path.normpath(project_dir + sep + script_path.key)

        dependency_tuple = GetProjectDependencies(project_file_path)
        if not dependency_tuple:
            return True
        
        project_dep_list = list(dependency_tuple)
        project_dep_list.sort()
        if script_path.values[0] != MakeHashFromString(' '.join(project_dep_list)):
            if args.verbose:
                print("Invalid: " + script_path.values[0])
            return False
    return True
    
    
def _CheckFiles(project_dir, hash_file_list, file_list):
    for hash_block in hash_file_list:
        if path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = path.normpath(hash_block.values[0])
        else:
            project_file_path = path.normpath(project_dir + sep + hash_block.values[0])
            
        if project_file_path not in file_list:
            if args.verbose:
                print("New project added to master file: " + hash_block.key)
            return False
    return True
    
    
def GetHashFilePath(project_path):
    return PosixPath(path.normpath(QPC_HASH_DIR + GetHashFileName(project_path)))
    
    
def GetHashFileName(project_path):
    hash_name = project_path.replace("/", ".")
    return hash_name + GetHashFileExt(hash_name)

    
def GetHashFileExt(project_path):
    if path.splitext(project_path)[1] == ".qpc":
        return "_hash"
    else:
        return ".qpc_hash"


def GetProjectDependencies(project_path: str) -> list:
    project_hash_file_path = GetHashFilePath(project_path)
    dep_list = []

    if path.isfile(project_hash_file_path):
        hash_file = qpc_reader.ReadFile(project_hash_file_path)

        if not hash_file:
            return dep_list

        for block in hash_file:
            if block.key == "dependencies":
                for dep_block in block.items:
                    # maybe get dependencies of that file as well? recursion?
                    dep_list.append(dep_block.key)
                    dep_list.extend(dep_block.values)
                break
    return dep_list


# TODO: change this to use QPC's ToString function in the lexer, this was made before that (i think)
def WriteHashFile(project_path: str, out_dir: str = "", hash_list=None, file_list=None,
                  master_file: bool = False, dependencies: dict = None) -> None:
    def ListToString(arg_list):
        if arg_list:
            return '"' + '" "'.join(arg_list) + '"\n'
        return "\n"
    
    with open(GetHashFilePath(project_path), mode="w", encoding="utf-8") as hash_file:
        # write the commands
        hash_file.write("commands\n{\n"
                        '\tworking_dir\t"' + getcwd().replace('\\', '/') + '"\n'
                        '\tout_dir\t\t"' + out_dir.replace('\\', '/') + '"\n')
        if not master_file:
            hash_file.write('\ttypes\t\t' + ListToString(args.types))
        else:
            hash_file.write('\tadd\t\t\t' + ListToString(args.add) +
                            '\tremove\t\t' + ListToString(args.remove))
        hash_file.write('\tmacros\t\t' + ListToString(args.macros) + "}\n\n")
        
        # write the hashes
        if hash_list:
            hash_file.write("hashes\n{\n")
            
            for project_script_path, hash_value in BASE_QPC_HASHES.items():
                hash_file.write('\t"' + hash_value + '" "' + project_script_path + '"\n')
            hash_file.write('\t\n')
            for project_script_path, hash_value in hash_list.items():
                hash_file.write('\t"' + hash_value + '" "' + project_script_path + '"\n')
                
            hash_file.write("}\n")
        
        if file_list:
            hash_file.write("files\n{\n")
            for script_hash_path, script_path in file_list.items():
                hash_file.write('\t"{0}"\t"{1}"\n'.format(script_path, script_hash_path))
            hash_file.write("}\n")

        if dependencies and not master_file:
            hash_file.write("\ndependencies\n{\n")
            for script_path in dependencies:
                hash_file.write('\t"{0}"\n'.format(script_path))
            hash_file.write("}\n")

        elif dependencies and master_file:
            hash_file.write("\nproject_dependencies\n{\n")
            for project, dependency_tuple in dependencies.items():
                dependency_list = list(dependency_tuple)
                dependency_list.sort()
                dependency_hash = MakeHashFromString(' '.join(dependency_list))
                hash_file.write('\t"{0}"\t"{1}"\n'.format(PosixPath(project), dependency_hash))
            hash_file.write("}\n")
    return

