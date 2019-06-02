const webpack = require('webpack')

defaults = {
    extensions: [
        '',
        '.webpack.js',
        '.web.js',
        '.js',
        '.coffee',
        '.cjsx',
        '.po'
    ],

    loaders: [
        {
            test: /\.coffee$/,
            loader: 'coffee-loader'
        },
        {
            test: /\.cjsx$/,
            loader: 'coffee-jsx-loader'
        },
        {
            test: /\.css$/,
            loader: 'style-loader!css-loader'
        },
        {
            test: /\.po$/,
            loader: 'json!po'
        }
    ]
}

function create_module(directory, name) {
    var module = {
        entry: './clients/apps/' + directory + '/' + name + '.cjsx',

        output: {
            path: './static/clients/apps/' + directory,
            filename: name + '.bundle.js',
            publicPath: 'static/clients/apps/' + directory
        },

        resolve: {
            extensions: defaults.extensions,
            modulesDirectories: [
                'clients',
                'node_modules'
            ]
        },

        module: {
            loaders: defaults.loaders
        },

        plugins: []
    }

    if (process.env.PRODUCTION) {
        module.plugins.push(
            new webpack.DefinePlugin({
                'process.env':{
                    'NODE_ENV': JSON.stringify('production')
                }
            })
        )
        module.plugins.push(
            new webpack.optimize.UglifyJsPlugin({
                compress: {
                    warnings: false,
                },
                output: {
                    comments: false,
                }
            })
        )

    } else {
        module.cache = true
        module.devtool = '#eval-source-map'
    }

    return module
}

module.exports = [
    create_module('expense', 'account'),
    create_module('expense', 'approve'),
    create_module('expense', 'categories'),
    create_module('expense', 'report'),
    create_module('purchase', 'verification'),
    create_module('izettle', 'overview'),
    create_module('accountspayable', 'accountspayable'),
    create_module('invoicing', 'invoice'),
    create_module('swish', 'swish'),
]
