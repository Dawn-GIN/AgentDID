// This is a Node.js script dedicated to resolving DIDs using the official library.

const { Resolver } = require('did-resolver');
const { getResolver } = require('ethr-did-resolver');
const { providers } = require('ethers'); // Import the ethers library

// 1. Receive arguments from the command line: Python will pass arguments here
// args[0] is the DID, args[1] is the API URL
const args = process.argv.slice(2);
const did = args[0];
const rpcUrl = args[1];

if (!did || !rpcUrl) {
    console.error("Error: Please provide a DID and an RPC URL");
    process.exit(1);
}

async function run() {
    try {
        // 2. Configure connection
        const providerConfig = {
            networks: [
                {
                    name: "sepolia",
                    rpcUrl: rpcUrl,
                    chainId: 11155111,
                    registry: "0x03d5003bf0e79C5F5223588F347ebA39AfbC3818"
                }
            ]
        };

        // 3. Initialize the official resolver
        const ethrDidResolver = getResolver(providerConfig);
        const didResolver = new Resolver(ethrDidResolver);

        // 4. Execute resolution (fetches data from the chain)
        const doc = await didResolver.resolve(did);

        // 5. Print the result as a JSON string (Python will capture this output)
        console.log(JSON.stringify(doc, null, 4));

    } catch (error) {
        console.error("Error during resolution:", error);
        process.exit(1);
    }
}

run();