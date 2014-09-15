jacks-context
=============

A script to automatically generate a context for passing into Jacks, including both constraints and canvas options.

== Requires ==

* geni-lib: [Source](https://bitbucket.org/barnstorm/geni-lib/src), [Install instructions](http://groups.geni.net/geni/wiki/HowTo/SetupGENILIB)

== Manifest ==

config.json -- Sample configuration file
jacks-context.py -- The script itself

== Usage ==

Make sure that you have a geni-lib config.py in the same directory as
your script. Run it as follows:

    jacks-context.py [-h] [--config CONFIG] [--output OUTPUT] [--basic]
                            site [site ...]

* `-h` help message
* `--config` points to the configuration file (optional)
* `--output` points to a file to dump results (defaults to stdout)
* `--basic` mode ignores types and options set as advanced in the
  configuration file.
* `site` is a geni-lib nickname for an IG aggregate (ex: ig-utah)

