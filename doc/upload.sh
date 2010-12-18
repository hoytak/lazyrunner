#!/bin/bash -e

make html
rsync -av -e ssh build/html/ hoytak@madrid.stat.washington.edu:~/public_html/code/lazyrunner/ 
ssh hoytak@madrid.stat.washington.edu "chmod -R a+rx ~/public_html/"
