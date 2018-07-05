#!/usr/bin/env python
# coding:utf8
"""
作者:pawn
邮箱:pawn9537@gmail.com
日期:18-6-20
时间:下午2:58
"""
import os, re
from datetime import datetime
from fabric.api import *

env.user = "pawn"
env.sudo_user = "root"
env.host = ['127.0.0.1']

db_user = "root"
db_password = "root"

_TAR_FILE = 'dist-awesome.tar.gz'

_REMOTE_BASE_DIR = '/srv/awesome'


def _current_path():
    return os.path.abspath('.')


def _now():
    return datetime.now().strftime("%y-%m-%d_%H.%M.%S")


def backup():
    """
    Dump entire database on server and backup to local.
    :return:
    """
    dt = _now()
    f = 'backup-awesome-%s.sql' % dt
    with cd('/tmp'):
        run(
            f'mysqldump --user={db_user} --password={db_password} --skip-opt --add-drop-table --default-character-set=utf-8 --quick awesone > {f}')
        run(f'tar -czvf {f}.tar.gz {f}')
        get(f"{f}.tar.gz", f'{_current_path()}/backup/')
        run(f'rm -f {f}')
        run(f"rm -f {f}.tar.gz")


def build():
    """
    Bulid dist package.
    :return:
    """
    includes = ['static', 'templates', 'transwarp', 'favicon.ico', '*.py']
    excludes = ['test', '.*', '*.pyc', '*.pyo']
    local(f'rm -f dist/{_TAR_FILE}')
    with lcd(os.path.join(_current_path(), 'www')):
        cmd = ['tar', '--dereference', '-czvf', f'../dist/{_TAR_FILE}']
        cmd.extend([f'--exclude={ex}' for ex in excludes])
        cmd.extend(includes)
        local(' '.join(cmd))


def deploy():
    newdir = f'www-{_now()}'
    run(f'rm -f {_REMOTE_BASE_DIR}')
    put(f'dist/{_TAR_FILE}', _REMOTE_BASE_DIR)
    with cd(_REMOTE_BASE_DIR):
        sudo(f'mkdir {newdir}')
    with cd(f'{_REMOTE_BASE_DIR}/{newdir}'):
        sudo(f'tar -xzvf {_REMOTE_BASE_DIR}')
    with cd(_REMOTE_BASE_DIR):
        sudo('rm -f www')
        sudo(f'ln -s {newdir}  www')
        sudo('chown www-data:www-data www')
        sudo(f'chown -R www-data:www-data {newdir}')
    with settings(warn_only=True):
        sudo('supervisorctl stop awesome')
        sudo('supervisorctl start awesome')
        sudo('/etc/init.d/nginx reload')


RE_FILES = re.compile('\r?\n')


def rollback():
    """
    rollback to previous version
    :return:
    """
    with cd(_REMOTE_BASE_DIR):
        r = run('ls -p -1')
        files = [s[:-1] for s in RE_FILES.split(r) if s.startswith('www-') and s.endswith('/')]
        files.sort(key=lambda s1, s2: 1 if s1 < s2 else -1)
        r = run('ls -l www')
        ss = r.split("->")
        if len(ss) != 2:
            print('ERROR: \'www\' is not a symbol link.')
            return
        current = ss[1]
        print(f'Found current symbol link points to {current}\n')
        try:
            index = files.index(current)
        except ValueError as e:
            print("ERROR: symbol link is invalid.")
            return
        if len(files) == index + 1:
            print('ERROR: already the oldest version.')

        old = files[index + 1]
        print('==================================================')
        for f in files:
            if f == current:
                print('      Current ---> %s' % current)
            elif f == old:
                print('  Rollback to ---> %s' % old)
            else:
                print('                   %s' % f)
        print('==================================================')
        print('')
        yn = input('continue? y/N ')
        if yn != 'y' and yn != 'Y':
            print('Rollback cancelled.')
            return

        print('Start rollback...')
        sudo('rm -f www')
        sudo('ln -s %s www' % old)
        sudo('chown www-data:www-data www')

        with settings(warn_only=True):
            sudo('supervisorctl stop awesome')
            sudo('supervisorctl start awesome')
            sudo('/etc/init.d/nginx reload')
        print('ROLLBACKED OK.')


def restore2local():
    """
    Restore db to local
    :return:
    """
    backup_dir = os.path.join(_current_path(), 'backup')
    fs = os.listdir(backup_dir)
    files = [f for f in fs if f.startswith('backup-') and f.endswith('.sql.tar.gz')]
    files.sort(key=lambda s1, s2: 1 if s1 < s2 else -1)
    if len(files) == 0:
        print('No backup files found.')
        return
    print('Found %s backup files:' % len(files))
    print('==================================================')
    n = 0
    for f in files:
        print('%s: %s' % (n, f))
        n = n + 1
    print('==================================================')
    print('')
    try:
        num = int(input('Restore file: '))
    except ValueError:
        print('Invalid file number.')
        return
    restore_file = files[num]
    yn = input('Restore file %s: %s? y/N ' % (num, restore_file))
    if yn != 'y' and yn != 'Y':
        print('Restore cancelled.')
        return
    print('Start restore to local database...')
    p = input('Input mysql root password: ')
    sqls = [
        'drop database if exists awesome;',
        'create database awesome;',
        'grant select, insert, update, delete on awesome.* to \'%s\'@\'localhost\' identified by \'%s\';' % (
        db_user, db_password)
    ]
    for sql in sqls:
        local(r'mysql -uroot -p%s -e "%s"' % (p, sql))
    with lcd(backup_dir):
        local('tar zxvf %s' % restore_file)
    local(r'mysql -uroot -p%s awesome < backup/%s' % (p, restore_file[:-7]))
    with lcd(backup_dir):
        local('rm -f %s' % restore_file[:-7])
