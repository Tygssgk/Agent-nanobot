import axios from "axios";

const BASE_URL = process.env.LITELLM_PROXY_URL;
const API_KEY = process.env.LITELLM_MASTER_KEY;

async function test() {
  try {
    const res = await axios.post(
      `${BASE_URL}/chat/completions`,
      {
        model: "gemini-flash",
        messages: [{ role: "user", content: "halo" }]
      },
      {
        headers: {
          Authorization: `Bearer ${API_KEY}`
        }
      }
    );

    console.log(res.data);
  } catch (err) {
    console.error(err.response?.data || err.message);
  }
}

test();
