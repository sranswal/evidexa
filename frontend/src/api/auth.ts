import { api, setAccessToken } from "./client";
import type { CaseMemberResponse, CaseRole, TokenResponse, User } from "../types/api";

export async function loginUser(usernameOrEmail: string, password: string): Promise<TokenResponse> {
  const tokens = await api.post<TokenResponse>("/auth/login", {
    username_or_email: usernameOrEmail,
    password,
  });
  setAccessToken(tokens.access_token);
  return tokens;
}

export async function registerUser(
  email: string,
  username: string,
  password: string,
  fullName: string
): Promise<User> {
  return api.post<User>("/auth/register", {
    email,
    username,
    password,
    full_name: fullName,
  });
}

export async function refreshSession(): Promise<TokenResponse> {
  const tokens = await api.post<TokenResponse>("/auth/refresh");
  setAccessToken(tokens.access_token);
  return tokens;
}

export async function logoutUser(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    setAccessToken(null);
  }
}

export async function fetchCurrentUser(): Promise<User> {
  return api.get<User>("/auth/me");
}

export async function listCaseMembers(caseId: string): Promise<CaseMemberResponse[]> {
  return api.get<CaseMemberResponse[]>(`/cases/${caseId}/members`);
}

export async function addCaseMember(
  caseId: string,
  userId: string,
  role: CaseRole
): Promise<CaseMemberResponse> {
  return api.post<CaseMemberResponse>(`/cases/${caseId}/members`, {
    user_id: userId,
    role,
  });
}

export async function removeCaseMember(caseId: string, userId: string): Promise<void> {
  return api.delete<void>(`/cases/${caseId}/members/${userId}`);
}

