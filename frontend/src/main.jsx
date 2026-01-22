import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import StateManage from "./StateManage.jsx";

const pathname = window.location.pathname;
const isStateManage = pathname === "/state-manage" || pathname.startsWith("/state-manage/");
const Root = isStateManage ? StateManage : App;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
