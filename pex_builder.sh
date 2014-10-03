reqs=$(cat requirements.txt)
reqs_args=''
for req in $reqs;
  do reqs_args+=" -r ${req}"
done

scripts=$(ls -1 *\.py)

tmpdir='/tmp/pex_builder'
for script in $scripts;
  do
    name=${script:0:-3}
    setup="from setuptools import setup\nsetup(name='$name',\n      version='1.0',\n      packages=['$name'],\n      entry_points={'console_scripts': ('$name = $name:main',)})"
    tmpdir2=$tmpdir/$name
    tmppkg=$tmpdir2/$name
    mkdir -p $tmppkg
    old_IFS=$IFS
    IFS=@
    echo -e $setup > $tmpdir2/setup.py
    IFS=$old_IFS
    cp $script $tmppkg/__init__.py
    cp maas_common.py $tmppkg
    pex --no-wheel -s $tmpdir2 -e "$name:main" $reqs_args -o "./$name.pex"
done
