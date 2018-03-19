# near

A utility like grep but finds all 'term2' near 'term1' across range of lines.
Additional terms may be specified.  Search terms are regular expressions.

Two terms are required, and both must be present
within that distance. This match is 'term1 AND term2'.
Additional terms may be supplied with "--or term".
In this case, it will be 'term1 AND (term2 OR term3 OR ...)'
By default, the matched range must start with term1. This is
'ordered' match. Specifying --no-ordered means that a match
range can start with any term.

Search terms are regular expressions.  


## Authors

* **Tom Biggs** - *Initial work* - [circularfire](https://github.com/circularfire)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
