const firebaseConfig = {
  apiKey: "AIzaSyAwCtVLR4PoG5lK1zafGXLNFgGs8-SfJzQ",
  authDomain: "skill-swap-india-b2a9a.firebaseapp.com",
  databaseURL: "https://skill-swap-india-b2a9a-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "skill-swap-india-b2a9a",
  storageBucket: "skill-swap-india-b2a9a.firebasestorage.app",
  messagingSenderId: "287890222992",
  appId: "1:287890222992:web:f2de60b76f3f5cf3f74d15",
  measurementId: "G-HHWKHMMRLY"
};

firebase.initializeApp(firebaseConfig);

const auth = firebase.auth();
const db = firebase.database();

// Make them available to your SkillSwap application
window.ssFirebase = {
  app: firebase.app(),
  auth: auth,
  db: db
};

window.ssFirebaseAuth = auth;
