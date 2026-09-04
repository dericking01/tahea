# -*- coding: utf-8 -*-

import os
import datetime
import time
import shutil
import json
import tempfile
import subprocess
import logging

import odoo
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, AccessDenied

_logger = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None
    _logger.info(
        "The auto_backup module needs the `paramiko` library to write backups "
        "to a remote server over SFTP. Install it with `pip install paramiko`."
    )


class DbBackup(models.Model):
    _name = 'db.backup'
    _description = 'Backup Configuration Record'

    @api.model
    def _get_db_name(self):
        return self.env.cr.dbname

    # Columns for local server configuration
    host = fields.Char('Host', required=True, default='localhost')
    port = fields.Char('Port', required=True, default='8069')
    name = fields.Char(
        'Database', required=True, default=lambda self: self._get_db_name(),
        help='Database you want to schedule backups for')
    folder = fields.Char(
        'Backup Directory', required=True, default='/odoo/backups',
        help='Absolute path for storing the backups')
    backup_type = fields.Selection(
        [('zip', 'Zip'), ('dump', 'Dump')],
        'Backup Type', required=True, default='zip')
    autoremove = fields.Boolean(
        'Auto. Remove Backups',
        help='If you check this option you can choose to automatically remove the '
             'backup after a number of days.')
    days_to_keep = fields.Integer(
        'Remove after x days', default=0,
        help="Choose after how many days the backup should be deleted. For example:\n"
             "If you fill in 5 the backups will be removed after 5 days.")

    # Columns for external server (SFTP)
    sftp_write = fields.Boolean(
        'Write to external server with SFTP',
        help="If you check this option you can specify the details needed to write "
             "to a remote server over SFTP.")
    sftp_path = fields.Char(
        'Path external server',
        help='The location of the folder where the dumps should be written to. For '
             'example /odoo/backups/.\nFiles will then be written to /odoo/backups/ '
             'on your remote server.')
    sftp_host = fields.Char(
        'IP Address SFTP Server',
        help='The IP address of your remote server. For example 192.168.0.1')
    sftp_port = fields.Integer(
        'SFTP Port', default=22,
        help='The port on the FTP server that accepts SSH/SFTP calls.')
    sftp_user = fields.Char(
        'Username SFTP Server',
        help='The username used for the SFTP connection. This is the user on the '
             'external server.')
    sftp_password = fields.Char(
        'Password User SFTP Server',
        help='The password of the user used for the SFTP connection. This is the '
             'password of the user on the external server.')
    days_to_keep_sftp = fields.Integer(
        'Remove SFTP after x days', default=30,
        help='Choose after how many days the backup should be deleted from the FTP '
             'server. For example:\nIf you fill in 5 the backups will be removed '
             'after 5 days from the FTP server.')
    send_mail_sftp_fail = fields.Boolean(
        'Auto. E-mail on backup fail',
        help='If you check this option you can choose to automatically get e-mailed '
             'when the backup to the external server fails.')
    email_to_notify = fields.Char(
        'E-mail to notify',
        help='Fill in the e-mail where you want to be notified that the backup '
             'failed on the FTP.')

    def _get_sftp_client(self, timeout=10):
        """Return a connected ``paramiko.SSHClient`` for the current record."""
        self.ensure_one()
        if paramiko is None:
            raise UserError(_(
                "The Python library `paramiko` is required for SFTP backups. "
                "Install it with `pip install paramiko` and restart the server."))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.sftp_host, port=self.sftp_port, username=self.sftp_user,
            password=self.sftp_password, timeout=timeout)
        return client

    def test_sftp_connection(self):
        self.ensure_one()

        client = None
        try:
            client = self._get_sftp_client(timeout=10)
            sftp = client.open_sftp()
            sftp.close()
        except UserError:
            raise
        except Exception as error:
            _logger.warning('There was a problem connecting to the remote SFTP: %s', error)
            message = _("Connection Test Failed!")
            if self.sftp_host and len(self.sftp_host) < 8:
                message += _("\nYour IP address seems to be too short.")
            message += _("\n\nHere is what we got instead:\n%s", tools.ustr(error))
            raise UserError(message)
        finally:
            if client is not None:
                client.close()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Connection Test Succeeded!"),
                'message': _("Everything seems properly set up for SFTP back-ups!"),
                'sticky': False,
            },
        }

    @api.model
    def schedule_backup(self):
        confs = self.search([])
        for rec in confs:
            try:
                if not os.path.isdir(rec.folder):
                    os.makedirs(rec.folder)
            except Exception:
                _logger.exception("Could not create the local backup directory %s", rec.folder)
                continue

            # Create name for dump file.
            bkp_file = '%s_%s.%s' % (time.strftime('%Y_%m_%d_%H_%M_%S'), rec.name, rec.backup_type)
            file_path = os.path.join(rec.folder, bkp_file)
            try:
                with open(file_path, 'wb') as fp:
                    self._take_dump(rec.name, fp, 'db.backup', rec.backup_type)
            except Exception as error:
                _logger.warning(
                    "Couldn't backup database %s. Bad database administrator password "
                    "for server running at http://%s:%s", rec.name, rec.host, rec.port)
                _logger.warning("Exact error from the exception: %s", error)
                continue

            if rec.sftp_write:
                rec._sftp_backup()

            # Remove all old files (on local server) in case this is configured.
            if rec.autoremove:
                rec._cleanup_local_backups()

    def _sftp_backup(self):
        """Push local backup files of this configuration to the remote SFTP server."""
        self.ensure_one()
        client = None
        sftp = None
        try:
            local_dir = self.folder
            path_to_write_to = self.sftp_path
            _logger.debug('sftp remote path: %s', path_to_write_to)

            client = self._get_sftp_client(timeout=20)
            sftp = client.open_sftp()

            try:
                sftp.chdir(path_to_write_to)
            except IOError:
                # Create directory and subdirs if they do not exist.
                current_directory = ''
                for dir_element in path_to_write_to.split('/'):
                    if not dir_element:
                        continue
                    current_directory += '/' + dir_element
                    try:
                        sftp.chdir(current_directory)
                    except IOError:
                        _logger.info(
                            "(Part of the) path didn't exist. Creating it now at %s",
                            current_directory)
                        sftp.mkdir(current_directory, 0o777)
                        sftp.chdir(current_directory)
            sftp.chdir(path_to_write_to)

            # Copy every local backup file that belongs to this database.
            for f in os.listdir(local_dir):
                if self.name not in f:
                    continue
                fullpath = os.path.join(local_dir, f)
                if not os.path.isfile(fullpath):
                    continue
                try:
                    sftp.stat(os.path.join(path_to_write_to, f))
                    _logger.debug('File %s already exists on the remote server ------ skipped', fullpath)
                except IOError:
                    try:
                        sftp.put(fullpath, os.path.join(path_to_write_to, f))
                        _logger.info('Copying file %s ------ success', fullpath)
                    except Exception as err:
                        _logger.critical("We couldn't write the file to the remote server. Error: %s", err)

            # Remove expired remote files.
            _logger.debug("Checking expired files")
            for file_name in sftp.listdir(path_to_write_to):
                if self.name not in file_name:
                    continue
                fullpath = os.path.join(path_to_write_to, file_name)
                timestamp = sftp.stat(fullpath).st_mtime
                create_time = datetime.datetime.fromtimestamp(timestamp)
                delta = datetime.datetime.now() - create_time
                if delta.days >= self.days_to_keep_sftp and (".dump" in file_name or '.zip' in file_name):
                    _logger.info("Delete too old file from SFTP server: %s", file_name)
                    sftp.unlink(file_name)
        except Exception as e:
            _logger.error(
                "Exception! We couldn't back up to the SFTP server. Here is what we "
                "got back instead: %s", e)
            if self.send_mail_sftp_fail:
                self._notify_sftp_failure(e)
        finally:
            if sftp is not None:
                try:
                    sftp.close()
                except Exception:
                    pass
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    def _notify_sftp_failure(self, error):
        """Send an e-mail notification that the SFTP backup failed."""
        self.ensure_one()
        if not self.email_to_notify:
            return
        try:
            ir_mail_server = self.env['ir.mail_server'].sudo().search(
                [], order='sequence asc', limit=1)
            if not ir_mail_server:
                _logger.warning("No outgoing mail server configured; cannot notify SFTP failure.")
                return
            message = _(
                "Dear,\n\nThe backup for the server %(host)s (IP: %(ip)s) failed.\n\n"
                "IP address SFTP server: %(ip)s\nUsername: %(user)s\n\n"
                "Error details: %(error)s\n\nWith kind regards",
                host=self.host, ip=self.sftp_host, user=self.sftp_user,
                error=tools.ustr(error))
            catch_all_domain = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")
            email_from = (
                "auto_backup@%s" % catch_all_domain if catch_all_domain
                else self.env.user.partner_id.email)
            msg = ir_mail_server.build_email(
                email_from, [self.email_to_notify],
                _("Backup from %(host)s (%(ip)s) failed", host=self.host, ip=self.sftp_host),
                message)
            ir_mail_server.send_email(msg)
        except Exception:
            _logger.exception("Could not send the SFTP backup failure notification e-mail.")

    def _cleanup_local_backups(self):
        """Delete local backup files of this configuration older than ``days_to_keep``."""
        self.ensure_one()
        directory = self.folder
        if not os.path.isdir(directory):
            return
        for f in os.listdir(directory):
            fullpath = os.path.join(directory, f)
            # Only delete the ones which are from the current database
            # (makes it possible to save different databases in the same folder).
            if self.name not in f:
                continue
            if not (os.path.isfile(fullpath) and (".dump" in f or '.zip' in f)):
                continue
            timestamp = os.stat(fullpath).st_ctime
            create_time = datetime.datetime.fromtimestamp(timestamp)
            delta = datetime.datetime.now() - create_time
            if delta.days >= self.days_to_keep:
                _logger.info("Delete local out-of-date file: %s", fullpath)
                os.remove(fullpath)

    # This is more or less the same as the default Odoo function at
    # odoo/service/db.py (dump_db). The main difference is that there is no wrapper
    # for check_db_management_enabled here and that authentication is based on the
    # cron user id and on checking that this is called for the 'db.backup' model.
    # Since this function is called from the cron and since these security checks
    # are enforced, it is practically impossible to abuse it to take a backup.
    # This allows disabling the Odoo database manager, which is a MUCH safer setup.
    def _take_dump(self, db_name, stream, model, backup_format='zip'):
        """Dump database ``db_name`` into file-like object ``stream``. If ``stream``
        is ``None`` return a file object with the dump."""

        cron_user_id = self.env.ref('auto_backup.backup_scheduler').user_id.id
        if self._name != 'db.backup' or cron_user_id != self.env.user.id:
            _logger.error('Unauthorized database operation. Backups should only be available from the cron job.')
            raise AccessDenied()

        _logger.info('DUMP DB: %s format %s', db_name, backup_format)

        # Connection settings (host/port/user/password) come from the Odoo config
        # via libpq environment variables, exactly like odoo.service.db.dump_db.
        # This is what makes pg_dump reach a remote/containerised PostgreSQL
        # instead of falling back to a local unix socket.
        pg_env = odoo.tools.exec_pg_environ()
        cmd = [odoo.tools.find_pg_tool('pg_dump'), '--no-owner', db_name]

        if backup_format == 'zip':
            with tempfile.TemporaryDirectory() as dump_dir:
                filestore = odoo.tools.config.filestore(db_name)
                if os.path.exists(filestore):
                    shutil.copytree(filestore, os.path.join(dump_dir, 'filestore'))
                with open(os.path.join(dump_dir, 'manifest.json'), 'w') as fh:
                    db = odoo.sql_db.db_connect(db_name)
                    with db.cursor() as cr:
                        json.dump(self._dump_db_manifest(cr), fh, indent=4)
                cmd.append('--file=' + os.path.join(dump_dir, 'dump.sql'))
                subprocess.run(cmd, env=pg_env, check=True)
                if stream:
                    odoo.tools.osutil.zip_dir(
                        dump_dir, stream, include_dir=False,
                        fnct_sort=lambda file_name: file_name != 'dump.sql')
                else:
                    t = tempfile.TemporaryFile()
                    odoo.tools.osutil.zip_dir(
                        dump_dir, t, include_dir=False,
                        fnct_sort=lambda file_name: file_name != 'dump.sql')
                    t.seek(0)
                    return t
        else:
            cmd.append('--format=c')
            process = subprocess.Popen(cmd, env=pg_env, stdout=subprocess.PIPE)
            stdout, _stderr = process.communicate()
            if process.returncode:
                raise Exception("pg_dump failed with return code %s" % process.returncode)
            if stream:
                stream.write(stdout)
            else:
                return stdout

    def _dump_db_manifest(self, cr):
        pg_version = "%d.%d" % divmod(cr._obj.connection.server_version // 100, 100)
        cr.execute("SELECT name, latest_version FROM ir_module_module WHERE state = 'installed'")
        modules = dict(cr.fetchall())
        manifest = {
            'odoo_dump': '1',
            'db_name': cr.dbname,
            'version': odoo.release.version,
            'version_info': odoo.release.version_info,
            'major_version': odoo.release.major_version,
            'pg_version': pg_version,
            'modules': modules,
        }
        return manifest
