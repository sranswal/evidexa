import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Logo } from "../components/brand/Logo";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { AuthProvider } from "../context/AuthContext";

// Mock API client for landing and auth views
vi.mock("../api/auth", () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  refreshSession: vi.fn().mockRejectedValue(new Error("No session")),
  logoutUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

describe("EVIDEXA Brand & Reusable Logo Component", () => {
  it("renders default horizontal lockup with icon and deliberate wordmark", () => {
    render(<Logo />);
    const icon = screen.getByAltText("EVIDEXA icon");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute("src", "/icon.png");

    expect(screen.getByText("EVID")).toBeInTheDocument();
    expect(screen.getByText("EXA")).toBeInTheDocument();
    expect(screen.getByText("Document Intelligence")).toBeInTheDocument();
  });

  it("renders icon-only variant without text", () => {
    render(<Logo variant="icon" />);
    expect(screen.getByAltText("EVIDEXA icon")).toBeInTheDocument();
    expect(screen.queryByText("EVID")).not.toBeInTheDocument();
    expect(screen.queryByText("Document Intelligence")).not.toBeInTheDocument();
  });

  it("renders compact variant without subtitle", () => {
    render(<Logo variant="compact" />);
    expect(screen.getByAltText("EVIDEXA icon")).toBeInTheDocument();
    expect(screen.getByText("EVID")).toBeInTheDocument();
    expect(screen.getByText("EXA")).toBeInTheDocument();
    expect(screen.queryByText("Document Intelligence")).not.toBeInTheDocument();
  });

  it("renders wordmark variant without icon image", () => {
    render(<Logo variant="wordmark" />);
    expect(screen.queryByAltText("EVIDEXA icon")).not.toBeInTheDocument();
    expect(screen.getByText("EVID")).toBeInTheDocument();
    expect(screen.getByText("EXA")).toBeInTheDocument();
  });

  it("renders full image lockup when useImageLockup is true", () => {
    render(<Logo useImageLockup />);
    const logoImg = screen.getByAltText("EVIDEXA Forensic Intelligence");
    expect(logoImg).toBeInTheDocument();
    expect(logoImg).toHaveAttribute("src", "/logo.png");
  });
});

describe("Public Website & Authentication Routing Separation", () => {
  it("renders public LandingPage at root path '/' without authentication", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/"]}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    // Verify presence of public landing page elements
    expect(screen.getByText(/The Forensic Workbench for/i)).toBeInTheDocument();
    expect(screen.getByText(/DIGITAL FORENSIC LIGHT TABLE/i)).toBeInTheDocument();
    expect(screen.getByText(/Launch Case Workspace/i)).toBeInTheDocument();
  });

  it("renders public LoginPage at '/login'", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/login"]}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(screen.getByText("Forensic Investigator Portal")).toBeInTheDocument();
    expect(screen.getByLabelText(/Username or Corporate Email/i)).toBeInTheDocument();
  });

  it("renders public RegisterPage at '/register'", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/register"]}>
            <Routes>
              <Route path="/register" element={<RegisterPage />} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(screen.getByText("Create Investigator Account")).toBeInTheDocument();
    expect(screen.getByLabelText(/Corporate \/ Agency Email/i)).toBeInTheDocument();
  });
});

