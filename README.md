# grommunio Admin API

[![project license](https://img.shields.io/github/license/grommunio/admin-api.svg)](LICENSE)
[![latest version](https://shields.io/github/v/tag/grommunio/admin-api)](https://github.com/grommunio/admin-api/tags)
[![code size](https://img.shields.io/github/languages/code-size/grommunio/admin-api)](https://github.com/grommunio/admin-api)

**grommunio Admin API is the central API component of grommunio managing appliance(s), domain(s), users(s) and more. grommunio API orchestrates any compontents and architectures required to operate and manage the entire grommunio stack.**

<details open="open">
<summary>Overview</summary>

- [About](#about)
  - [Built with](#built-with)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Status](#status)
- [Support](#support)
- [Project assistance](#project-assistance)
- [Contributing](#contributing)
- [Security](#security)
- [Coding style](#coding-style)
- [License](#license)

</details>

---

## About grommunio Admin API

- [OpenAPI 3.0](https://swagger.io/specification/) based REST API and interactive CLI
- Web-based access via [grommunio Admin Web](https://github.com/grommunio/admin-web)
- Management of grommunio components
- User, group and mailing list management
- User synchronization with LDAP-capable backends
- Account-retrieval via fetchmail
- Public Folder management
- Role management with System, Organization and Domain roles
- Tenant management with organizations and domains
- Configuration through grommunio-dbconf
- Realtime connection status incl. mobile devices
- Log Viewer
- Mail transport queue and Task queue
- Distributable, compatible with load balancers such as haproxy, apisix, KEMP and others
- Secure, with extended security checks and CSRF tokens

## Getting Started

### Prerequisites

- `uwsgi` application server with `uwsgi-python3` plugin
- `MySQL` or `MariaDB` database server as central storage (as used and set up by [gromox](https://github.com/grommunio/gromox))
- `python3-pyexmdb` for gromox store management (provided by [libexmdbpp](https://github.com/grommunio/libexmdbpp))
- Recommended: a web server with a working TLS configuration (e.g. `nginx`)

### Installation

- Install required packages listed in the [Pipfile](Pipfile), either as system packages or in a virtual environment
- Deploy admin-api at a location of your choice, such as `/usr/share/grommunio-admin-api`
- Configure [database connection](conf.d/README.md#Database)
- Customize [configuration](conf.d/README.md) as needed
- Run the [main.py](main.py) file with `uwsgi` ([example configuration](data/api-config.ini), [documentation](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html))

## Usage

- Use the grommunio Admin API CLI reference for operation from [https://docs.grommunio.com/man/grommunio-admin.html](https://docs.grommunio.com/man/grommunio-admin.html)

or

- Use your API client to generate calls, based on [OpenAPI specification](res/openapi.yaml)

## Support

- Support is available through **[grommunio GmbH](https://grommunio.com)** and its partners.
- grommunio Admin API community is available here: **[grommunio Community](https://community.grommunio.com)**

For direct contact to the maintainers (for example to supply information about a security-related responsible disclosure), you can contact grommunio directly at [dev@grommunio.com](mailto:dev@grommunio.com)

## Contributing

First off, thanks for taking the time to contribute! Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make will benefit everybody else and are greatly appreciated.

Please read [our contribution guidelines](doc/CONTRIBUTING.md), and thank you for being involved!

## Security

grommunio Admin API follows good practices of security. grommunio constantly monitors security related issues.
grommunio Admin API is provided "as is" without any warranty. For professional support options through subscriptions, head over to [grommunio](https://grommunio.com).

_For more information and to report security issues, please refer to our [security documentation](doc/SECURITY.md)._

## Coding style

This repository follows coding style loosely based on PEP8 standard (exception: maximum line width of 127).

## License

This project is licensed under the **GNU Affero General Public License v3**.

See [LICENSE](LICENSE.txt) for more information.
