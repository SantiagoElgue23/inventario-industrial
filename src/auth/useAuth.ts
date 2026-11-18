import { createContext, useContext } from 'react';

export type Role = 'master' | 'admin' | 'user';
export type Account = { username: string; role: Role };
export type AuthContextType = {
  account: Account | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  canViewPrices: boolean;
  canEditPrices: boolean;
  canArchive: boolean;
  canAdminister: boolean;
};

export const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth requiere AuthProvider');
  return context;
}
