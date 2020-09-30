const axios = require("axios").default;
const SocksAgent = require('axios-socks5-agent')

let url = "https://www.google.com";

const { httpAgent, httpsAgent } = new SocksAgent({
    port: 1080
})

axios
    .get(url, { httpAgent, httpsAgent,
        headers: {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
            // "Cookie": "_fbp=fb.2.1601373309678.132341132; _ga=GA1.3.2005732690.1601373301; _gcl_au=1.1.830223684.1601373294; _gid=GA1.3.1982652367.1601373301; _uetsid=0a427ae286aeb798eedd442e634d1763; _uetvid=f318bb4d859676dcd660c6da766d8a0c; cidgenerated=1; cmp.ret.enq.afgtoken=CfDJ8Efs2BAxx71EoBhTrHnI3sPDm7KnlbrLH82gTRe9hB0H9xSP48iFk9ye9r_lGu7gOWTy54vsTAUSjokIo12LT85Wfku6lM5HC2XXTTbDK5wHDw83OC85MWutwn-jLRph2u6tVEvvdPnmoe0G1E7zoVQ; csn.bi=1601373291335; csncidcf=36E3AF91-630C-41B4-8A03-91678E5D2E51; csnclientid=EA56AF7C-0959-4FC1-816F-D87F17AE6564; datadome=KagJ9yL65Lj8iQ49u2E87FzpN7KOBg84qaEKBFczrvPuxqKxdxqh7wM4Ev6c9d.wKPCVs3MrVU.Ykx_4faSxhDZGivb9-ptkg91NMa5c9; DeviceId=145809cd-b31a-4dea-9734-1013f98a1345; gaclientId=2005732690.1601373301; gdpr:accept:EU=true;"
        },

              })
  .then(res => console.log(res.data))
  .catch(e => console.error(e))
