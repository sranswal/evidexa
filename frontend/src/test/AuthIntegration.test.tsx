import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { LoginPage } from "../pages/LoginPage";
import { Header } from "../components/layout/Header";
import { CaseProvider } from "../context/CaseContext";
import * as authApi from "../api/auth";

vi.mock("../api/auth", () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  refreshSession: vi.fn(),
  logoutUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
}));

describe("Enterprise Authentication & RBAC Frontend Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated user to /login", async () => {
    vi.mocked(authApi.refreshSession).mockRejectedValueOnce(new Error("No active session"));

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/cases"]}>
          <Routes>
            <Route path="/login" element={<div data-testid="login-page">Login Page</div>} />
            <Route
              path="/cases"
              element={
                <ProtectedRoute>
                  <div data-testid="cases-page">Protected Cases Workspace</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("login-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("cases-page")).not.toBeInTheDocument();
  });

  it("submits login form and navigates to protected workspace upon success", async () => {
    const mockUser = {
      id: "usr-investigator-01",
      email: "investigator@evidexa.test",
      username: "investigator",
      full_name: "Investigator John Doe",
      is_active: true,
      system_role: "USER" as const,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    vi.mocked(authApi.refreshSession).mockRejectedValueOnce(new Error("No session"));
    vi.mocked(authApi.loginUser).mockResolvedValueOnce({
      access_token: "mock-access-token",
      refresh_token: "mock-refresh-token",
      token_type: "bearer",
      expires_in: 900,
      user: mockUser,
    });

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/cases" element={<div data-testid="cases-page">Protected Cases Workspace</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/examiner@agency\.gov or username/i)).toBeInTheDocument();
    });

    const userInput = screen.getByPlaceholderText(/examiner@agency\.gov or username/i);
    const passInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole("button", { name: /Sign In to Investigation Workspace/i });

    fireEvent.change(userInput, { target: { value: "investigator" } });
    fireEvent.change(passInput, { target: { value: "SecurePass123!" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(authApi.loginUser).toHaveBeenCalledWith("investigator", "SecurePass123!");
      expect(screen.getByTestId("cases-page")).toBeInTheDocument();
    });
  });

  it("displays generic security error message when authentication fails", async () => {
    vi.mocked(authApi.refreshSession).mockRejectedValueOnce(new Error("No session"));
    vi.mocked(authApi.loginUser).mockRejectedValueOnce(new Error("Invalid username or password."));

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/examiner@agency\.gov or username/i)).toBeInTheDocument();
    });

    const userInput = screen.getByPlaceholderText(/examiner@agency\.gov or username/i);
    const passInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole("button", { name: /Sign In to Investigation Workspace/i });

    fireEvent.change(userInput, { target: { value: "invalid_user" } });
    fireEvent.change(passInput, { target: { value: "wrongpassword" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Invalid username or password|Unable to authenticate/i)).toBeInTheDocument();
    });
  });

  it("renders user profile, system role, and executes logout in Header", async () => {
    const mockUser = {
      id: "usr-admin-01",
      email: "admin@evidexa.test",
      username: "superadmin",
      full_name: "Lead Forensic Examiner",
      is_active: true,
      system_role: "SYSTEM_ADMIN" as const,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    vi.mocked(authApi.refreshSession).mockResolvedValueOnce({
      access_token: "mock-access-token",
      refresh_token: "mock-refresh-token",
      token_type: "bearer",
      expires_in: 900,
      user: mockUser,
    });
    vi.mocked(authApi.logoutUser).mockResolvedValueOnce();

    render(
      <AuthProvider>
        <CaseProvider>
          <MemoryRouter initialEntries={["/cases"]}>
            <Header />
          </MemoryRouter>
        </CaseProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Lead Forensic Examiner")).toBeInTheDocument();
      expect(screen.getByText("SYSTEM_ADMIN")).toBeInTheDocument();
    });

    const logoutBtn = screen.getByTitle("Sign Out");
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(authApi.logoutUser).toHaveBeenCalled();
      expect(screen.queryByText("Lead Forensic Examiner")).not.toBeInTheDocument();
    });
  });
});
