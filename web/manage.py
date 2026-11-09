#!/usr/bin/env python
"""Utilitário de linha de comando do Django."""
import os
import sys


def principal():
    os.environ.setdefault("DEBUG", "1")  # desenvolvimento local; em produção o padrão é False
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "site_conferencia.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    principal()
