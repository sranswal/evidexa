import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";

describe("AppShell Component", () => {
  it("renders brand mark, navigation links, and child routes", () => {
    render(
      <MemoryRouter initialEntries={["/cases"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/cases" element={<div>Cases Content Page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    // Verify brand
    expect(screen.getByText("EVID")).toBeInTheDocument();
    expect(screen.getByText("EXA")).toBeInTheDocument();
    expect(screen.getByText("Document Intelligence")).toBeInTheDocument();

    // Verify nav links
    expect(screen.getByText("All Cases")).toBeInTheDocument();

    // Verify child route content
    expect(screen.getByText("Cases Content Page")).toBeInTheDocument();

    // Verify footer status
    expect(screen.getByText("EVIDEXA Core v0.1.0")).toBeInTheDocument();
  });
});
