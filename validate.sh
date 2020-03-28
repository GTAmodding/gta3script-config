#!/bin/bash
cd config
rnv ../schema.rnc $(find -type f -name '*.xml')
