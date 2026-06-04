{-# LANGUAGE LambdaCase #-}

-- | Haskell-frontend: компилирует модуль до GHC Core (выход десугарера) и
-- печатает его в общем IR (sexpr, см. docs/common-ir.md).
module Main (main) where

import System.Environment (getArgs)
import Data.Char (isSpace)
import Data.List (intercalate)

import GHC
import GHC.Paths (libdir)
import GHC.Core
import GHC.Core.DataCon (dataConName)
import GHC.Types.Var (Var, varType, isGlobalId, isTyVar, isId)
import GHC.Types.Name (getOccString)
import GHC.Types.Literal (Literal (..))
import GHC.Unit.Module.ModGuts (ModGuts (..))
import GHC.Unit.Module.Graph (mgModSummaries)
import GHC.Utils.Outputable (ppr, showSDocUnsafe)

-- ---------------------------------------------------------------------------
-- Driver
-- ---------------------------------------------------------------------------

main :: IO ()
main = do
  args <- getArgs
  case args of
    [path] -> compileToCore path >>= putStrLn . renderModule
    _      -> putStrLn "usage: core-to-ir <File.hs>"

compileToCore :: FilePath -> IO [CoreBind]
compileToCore path = runGhc (Just libdir) $ do
  dflags <- getSessionDynFlags
  _ <- setSessionDynFlags dflags
  target <- guessTarget path Nothing Nothing
  setTargets [target]
  _ <- load LoadAllTargets
  graph <- getModuleGraph
  let modSum = head (mgModSummaries graph)
  dmod <- parseModule modSum >>= typecheckModule >>= desugarModule
  pure (mg_binds (coreModule dmod))

-- ---------------------------------------------------------------------------
-- Core -> sexpr
-- ---------------------------------------------------------------------------

renderModule :: [CoreBind] -> String
renderModule binds = "(module " ++ unwords (concatMap renderBind binds) ++ ")"

renderBind :: CoreBind -> [String]
renderBind = \case
  NonRec b e -> [renderDef b e | userBind b]
  Rec pairs  -> [renderDef b e | (b, e) <- pairs, userBind b]

-- Отсекаем компиляторно-генерируемые биндинги (Typeable/TyCon-метаданные,
-- словари классов): их имена начинаются с '$'.
userBind :: Var -> Bool
userBind b = case getOccString b of
  '$' : _ -> False
  _       -> True

renderDef :: Var -> CoreExpr -> String
renderDef b e =
  "(def " ++ getOccString b ++ " " ++ renderType (varType b) ++ " " ++ renderExpr e ++ ")"

renderExpr :: CoreExpr -> String
renderExpr = \case
  Var v          -> "(" ++ (if isGlobalId v then "const" else "var") ++ " " ++ getOccString v ++ ")"
  Lit l          -> renderLit l
  App f a        -> case a of
                      Type _     -> renderExpr f   -- отбрасываем тип-аргумент
                      Coercion _ -> renderExpr f   -- отбрасываем коэрцию
                      _          -> "(app " ++ renderExpr f ++ " " ++ renderExpr a ++ ")"
  Lam b body
    | isTyVar b  -> renderExpr body                -- отбрасываем тип-лямбду
    | otherwise  -> "(lam (" ++ getOccString b ++ " " ++ renderType (varType b)
                              ++ ") " ++ renderExpr body ++ ")"
  Let bnd body   -> renderLet bnd body
  Case s _ _ alts -> "(case " ++ renderExpr s ++ " " ++ unwords (map renderAlt alts) ++ ")"
  Cast e _       -> renderExpr e                   -- отбрасываем cast
  Tick _ e       -> renderExpr e                   -- отбрасываем tick
  Type t         -> renderType t
  Coercion _     -> "(const _coercion)"

renderLet :: CoreBind -> CoreExpr -> String
renderLet (NonRec b rhs) body =
  "(let (" ++ getOccString b ++ " " ++ renderType (varType b) ++ " " ++ renderExpr rhs
           ++ ") " ++ renderExpr body ++ ")"
renderLet (Rec pairs) body = go pairs
  where
    -- рекурсивный let разворачиваем в цепочку (семантику рекурсии теряем — для PoC ок)
    go [] = renderExpr body
    go ((b, rhs) : rest) =
      "(let (" ++ getOccString b ++ " " ++ renderType (varType b) ++ " " ++ renderExpr rhs
               ++ ") " ++ go rest ++ ")"

renderAlt :: CoreAlt -> String
renderAlt (Alt con bs rhs) = "(alt " ++ renderPat con bs ++ " " ++ renderExpr rhs ++ ")"

renderPat :: AltCon -> [Var] -> String
renderPat con bs = case con of
  DataAlt dc -> "(pcon " ++ getOccString (dataConName dc)
                         ++ " (" ++ unwords (map getOccString (filter isId bs)) ++ "))"
  LitAlt l   -> "(plit " ++ litParts l ++ ")"
  DEFAULT    -> "(pwild)"

renderLit :: Literal -> String
renderLit l = "(lit " ++ litParts l ++ ")"

litParts :: Literal -> String
litParts = \case
  LitNumber _ i -> show i ++ " int"
  LitChar c     -> show (fromEnum c) ++ " char"
  LitString bs  -> sanitize (show bs) ++ " str"
  other         -> sanitize (showSDocUnsafe (ppr other)) ++ " lit"

renderType :: Type -> String
renderType t = "(const " ++ sanitize (showSDocUnsafe (ppr t)) ++ ")"

-- Тип/литерал -> безопасный атом sexpr (без пробелов и скобок).
sanitize :: String -> String
sanitize = filter (\c -> not (isSpace c) && c /= '(' && c /= ')')
