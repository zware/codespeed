# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import datetime
from subprocess import Popen, PIPE
import logging

from django.conf import settings

from .exceptions import CommitLogError

logger = logging.getLogger(__name__)


class Mercurial:
    def __init__(self, project):
        self.project = project

    def update_repo(self, update=True):
        project = self.project
        if os.path.exists(project.working_copy):
            if not update:
                return

            p = Popen(['hg', 'pull', '-u'], stdout=PIPE, stderr=PIPE,
                        cwd=project.working_copy)
            stdout, stderr = p.communicate()

            if p.returncode != 0 or stderr:
                raise CommitLogError("hg pull returned %s: %s" % (p.returncode,
                                                                  stderr))
            else:
                return [{'error': False}]
        else:
            # Clone repo
            cmd = ['hg', 'clone', project.repo_path, project.repo_name]

            p = Popen(cmd, stdout=PIPE, stderr=PIPE,
                        cwd=settings.REPOSITORY_BASE_PATH)
            logger.debug('Cloning Mercurial repo {0} for project {1}'.format(
                project.repo_path, project))
            stdout, stderr = p.communicate()

            if p.returncode != 0:
                raise CommitLogError("%s returned %s: %s" % (" ".join(cmd),
                                                             p.returncode,
                                                             stderr))
            else:
                return [{'error': False}]

    def get_logs(self, endrev, startrev):
        self.update_repo(update=False)

        cmd = ["hg", "log",
                "-r", "%s::%s" % (startrev.commitid, endrev.commitid),
                "--template", "{rev}:{node|short}\n{node}\n{author|user}\n{author|email}\n{date}\n{desc}\n=newlog=\n"]

        working_copy = self.project.working_copy
        p = Popen(cmd,
                  stdout=PIPE, stderr=PIPE,
                  universal_newlines=True,
                  cwd=working_copy)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
            raise CommitLogError(str(stderr))
        else:
            stdout = stdout.rstrip('\n')  # Remove last newline
            logs = []
            for log in stdout.split("=newlog=\n"):
                elements = []
                elements = log.split('\n')[:-1]
                if len(elements) < 6:
                    # "Malformed" log
                    logs.append(
                        {'date': '-', 'message': 'error parsing log', 'commitid': '-'})
                else:
                    short_commit_id = elements.pop(0)
                    commit_id = elements.pop(0)
                    author_name = elements.pop(0)
                    author_email = elements.pop(0)
                    date = elements.pop(0)
                    # All other newlines should belong to the description text. Join.
                    message = '\n'.join(elements)

                    # Parse date
                    date = date.split('-')[0]
                    date = datetime.datetime.fromtimestamp(float(date)).strftime("%Y-%m-%d %H:%M:%S")

                    # Add changeset info
                    logs.append({
                        'date': date, 'author': author_name,
                        'author_email': author_email, 'message': message,
                        'short_commit_id': short_commit_id, 'commitid': commit_id})
        # Remove last log here because mercurial saves the short hast as commitid now
        if len(logs) > 1 and logs[-1].get('short_commit_id') == startrev.commitid:
            logs.pop()
        return logs

    def get_commit_date(self, commit_id):
        self.update_repo(update=False)

        cmd = ["hg", "log", "-r", commit_id, "--template", "{date|rfc3339date}\n"]

        p = Popen(cmd,
                  stdout=PIPE, stderr=PIPE,
                  universal_newlines=True,
                  cwd=self.project.working_copy)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
            raise CommitLogError(str(stderr))

        return stdout.rstrip()
