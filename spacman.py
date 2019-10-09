#!/usr/bin/python3

import os
import ctypes
import sys
import argparse


default_conf_file = os.path.expanduser('~') + '/.config/spacman.conf'


libalpm = ctypes.CDLL('libalpm.so')
alpm_pkg_vercmp = libalpm.alpm_pkg_vercmp


def vercmp(v1, v2):
    return alpm_pkg_vercmp(ctypes.c_char_p(v1.encode()),ctypes.c_char_p(v2.encode()))


def err(s):
    sys.stderr.write(s + '\n')


def conv_pkg_info(pkg_info_str):
    return [pkg_info_str[0][1], [pkg_info_str[1][1], pkg_info_str[7][1].split(), pkg_info_str[8][1].split()]]


def get_system_pkgs():
    
    # Query all package's information
    pkg_info_list = os.popen('LANG=C pacman -Qi').read().strip().replace(' None', '').split('\n\n')
    pkg_item_info_dict = dict(map(
        lambda i:conv_pkg_info(list(map(
            lambda l:list(map(
                lambda ll:ll.strip(),
                l.split(':'))),
            i.split('\n')))),
        pkg_info_list))
    
    # statistic the provider
    pkg_provider_dict = dict()
    for pkg in pkg_item_info_dict:
        provider_list = list(map(lambda x:x.split('='), pkg_item_info_dict[pkg][1]))
        for provider in provider_list:
            if provider[0] not in pkg_provider_dict:
                pkg_provider_dict[provider[0]] = dict()
            if len(provider) == 1:
                pkg_provider_dict[provider[0]][''] = pkg
            else:
                pkg_provider_dict[provider[0]][provider[1]] = pkg
    
    # replace all depends to real package name
    for pkg in pkg_item_info_dict:
        for i in range(len(pkg_item_info_dict[pkg][2])):
            needstr = pkg_item_info_dict[pkg][2][i]
            need = needstr.split('=')[0].split('>')[0].split('<')[0]

            if len(needstr) == len(need):
                if need not in pkg_item_info_dict and need in pkg_provider_dict:
                    for v in pkg_provider_dict[need]:
                        pkg_item_info_dict[pkg][2][i] = pkg_provider_dict[need][v]
                        break
            else:
                for op in ['<=', '>=', '<', '>', '=']:
                    need = needstr.split(op)
                    if len(need) != 1:
                        break;
                if len(need) == 1:
                    err(':: \033[1;33m' + pkg + '\033[0m : The dependency ' + needstr + " can't be reconize.")
                    continue
                
                if op == '=':
                    op = '=='
                
                if need[0] in pkg_item_info_dict:
                    pkg_item_info_dict[pkg][2][i] = need[0]
                elif need[0] in pkg_provider_dict:
                    for ver in pkg_provider_dict[need[0]]:
                        cmpr = eval('vercmp(ver, need[1]) ' + op + ' 0')
                        if cmpr:
                            pkg_item_info_dict[pkg][2][i] = pkg_provider_dict[need[0]][ver]
                            ver = None
                            break
                    if ver is not None:
                        err(':: \033[1;33m' + pkg + '\033[0m : The dependency ' + needstr + " can't be satisfied.")
                else:
                    err(':: \033[1;33m' + pkg + '\033[0m : The dependency ' + needstr + " can't be reconize.")
                continue

    # check
    missing_package = []
    for pkg in pkg_item_info_dict:
        for q_pkg in pkg_item_info_dict[pkg][2]:
            if q_pkg not in pkg_item_info_dict:
                missing_package.append([q_pkg, pkg])
    if len(missing_package) > 0:
        for mdep in missing_package:
            err(':: \033[1;33m' + mdep[1] + '\033[0m : The dependency \033[1;33m' + mdep[0] + "\033[0m can't be satisfied. Missing dependency package. Please install it and try again.")
        exit(0)
    
    return pkg_item_info_dict




def get_pkglist_recursive_needs(system_pkg_info, pkglist):
    result = set()
    query_invalid_result = list()
    
    def add_pkg_recursive_needs(pkglist_):
        for pkg in pkglist_:
            if not pkg in result:
                if pkg in system_pkg_info:
                    result.add(pkg)
                    add_pkg_recursive_needs(system_pkg_info[pkg][2])
                else:
                    query_invalid_result.append(pkg)

    add_pkg_recursive_needs(pkglist)
    return (result, query_invalid_result)


def get_conf_set(config):
    lines = open(config).readlines()
    s_set = set()
    for line in lines:
        elem = line.split('#', 1)[0].strip()
        if len(elem) != 0:
            s_set.add(elem)
    return s_set


def main(args):
    if not os.path.exists(args.config):
        err('No such file: ' + args.config)
        return 1
    
    # Read configure file
    pkg_needs_config = get_conf_set(args.config)
    if args.query:
        print('\n'.join(pkg_needs_config))
        return
    
    # Read all packages of local system.
    system_pkg_info = get_system_pkgs()
    pkg_in_system = {pkg for pkg in system_pkg_info}
    
    (pkg_needs_in_system, pkg_needs_install) = get_pkglist_recursive_needs(system_pkg_info, pkg_needs_config)
    pkg_noneeds_in_system = pkg_in_system - pkg_needs_in_system
    
    if args.apply:
        if len(pkg_noneeds_in_system) > 0:
            os.system(args.pacman + ' -R ' + ' '.join(pkg_noneeds_in_system))
        if len(pkg_needs_install) > 0:
            os.system(args.pacman + ' -S ' + ' '.join(pkg_needs_install))
        return
    
    print('Following ' + str(len(pkg_noneeds_in_system)) + ' packages need to be uninstalled:')
    print('\033[1;33m' + ' '.join(pkg_noneeds_in_system) + '\033[0m')
    print()
    print('Following ' + str(len(pkg_needs_install)) + ' packages need to be installed:')
    print('\033[1;32m' + ' '.join(pkg_needs_install) + '\033[0m')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Super package manager for archlinux.")
    parser.add_argument('--config', '-c', help='Specify the package list file.', default=default_conf_file)
    parser.add_argument('--pacman', '-p', help='Specify the package management.', default='sudo pacman')
    parser.add_argument('--apply', '-a', help='Call package manager to apply to system.', action='store_const', const=True, default=False)
    parser.add_argument('--query', '-q', help='Query packages from the configure file.', action='store_const', const=True, default=False)
    args = parser.parse_args()
    
    exit(main(args))
