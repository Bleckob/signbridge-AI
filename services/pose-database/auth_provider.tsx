// supabase authentication context
// React AuthProvider context that wraps the app
// this code is here a template for the frontend


// import { createContext, useContext, useEffect, useState } from "react"
// import { createClient, Session } from "@supabase/supabase-js"

// export const supabase = createClient(
//   process.env.NEXT_PUBLIC_SUPABASE_URL!,
//   process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
// )

// const AuthContext = createContext<{ session: Session | null }>({ session: null })

// export function AuthProvider({ children }: { children: React.ReactNode }) {
//   const [session, setSession] = useState<Session | null>(null)

//   useEffect(() => {
//     supabase.auth.getSession().then(({ data: { session } }) => setSession(session))
//     const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
//       setSession(session)
//     })
//     return () => subscription.unsubscribe()
//   }, [])

//   return <AuthContext.Provider value={{ session }}>{children}</AuthContext.Provider>
// }

// export const useAuth = () => useContext(AuthContext)